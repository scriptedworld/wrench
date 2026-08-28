//! The YAML codec: bytes to a value, and a value to canonical bytes.
//!
//! Canonical form is block style, one key to a line, keys sorted, and a scalar
//! quoted exactly when it is meant to be a string. Booleans and numbers stay
//! bare. Quoting marks intent, so `no`, `1.20` and `null` survive a round trip
//! as the strings they were.
//!
//! The emitter is written here rather than handed to a library, as it is in the
//! Go and Python packs. `testdata/canonical/` defines the form and no YAML
//! emitter produces it: they quote what would be ambiguous, which is the
//! opposite rule to quoting by what the value is.
//!
//! Only the parser is bound, to yaml-rust2.

use serde_json::{Map, Value};
use yaml_rust2::{yaml::Yaml, YamlLoader};

use crate::errors::Message;

const INDENT: usize = 2;

/// A format, knowing nothing about where the bytes came from.
pub trait Codec {
    fn decode(&self, data: &[u8]) -> Result<Value, Box<dyn std::error::Error + Send + Sync>>;
    fn encode(&self, value: &Value) -> Result<Vec<u8>, Box<dyn std::error::Error + Send + Sync>>;
}

/// The YAML codec that ships.
pub struct YamlCodec;

/// The one instance callers use.
pub const YAML: YamlCodec = YamlCodec;

impl Codec for YamlCodec {
    fn decode(&self, data: &[u8]) -> Result<Value, Box<dyn std::error::Error + Send + Sync>> {
        let text = std::str::from_utf8(data)?;
        let documents = YamlLoader::load_from_str(text)?;
        match documents.len() {
            0 => Ok(Value::Null),
            1 => Ok(normalise(&documents[0])?),
            n => Err(Box::new(Message(format!(
                "{n} documents in one file, want exactly one"
            )))),
        }
    }

    fn encode(&self, value: &Value) -> Result<Vec<u8>, Box<dyn std::error::Error + Send + Sync>> {
        Ok(canonical(value, 0)?.into_bytes())
    }
}

/// What the parser produced, in the shape a JSON Schema validator expects.
///
/// FR-2.9: maps, lists and JSON scalars, and nothing else. A mapping key that is
/// not a string has no JSON equivalent and is refused rather than coerced,
/// because coercing invents a document nobody wrote.
fn normalise(node: &Yaml) -> Result<Value, Box<dyn std::error::Error + Send + Sync>> {
    Ok(match node {
        Yaml::Null | Yaml::BadValue => Value::Null,
        Yaml::Boolean(b) => Value::Bool(*b),
        Yaml::Integer(i) => Value::Number((*i).into()),
        Yaml::Real(text) => real(text)?,
        Yaml::String(s) => Value::String(s.clone()),
        Yaml::Array(items) => {
            let mut out = Vec::with_capacity(items.len());
            for item in items {
                out.push(normalise(item)?);
            }
            Value::Array(out)
        }
        Yaml::Hash(pairs) => {
            let mut out = Map::new();
            for (key, item) in pairs {
                let name = key.as_str().ok_or_else(|| {
                    Message(format!("mapping key {key:?} is not a string"))
                })?;
                out.insert(name.to_string(), normalise(item)?);
            }
            Value::Object(out)
        }
        Yaml::Alias(_) => {
            return Err(Box::new(Message(
                "an alias has no JSON equivalent and is refused rather than expanded".into(),
            )))
        }
    })
}

/// A YAML real, refused where JSON has no way to say it.
fn real(text: &str) -> Result<Value, Box<dyn std::error::Error + Send + Sync>> {
    let parsed: f64 = text.parse()?;
    // NaN and the infinities are refused: YAML can spell them and JSON Schema
    // cannot represent them, so a file carrying one is a file no consumer in
    // this ecosystem can validate.
    serde_json::Number::from_f64(parsed)
        .map(Value::Number)
        .ok_or_else(|| {
            Box::new(Message(format!("cannot represent {text} in canonical form")))
                as Box<dyn std::error::Error + Send + Sync>
        })
}

/// Where in the structure a failure happened, so a caller can find the value.
/// The Go and Python packs word it identically; a message that differs by pack
/// is one a consumer cannot be told to look for.
fn at(where_: String, error: Box<dyn std::error::Error + Send + Sync>) -> Box<dyn std::error::Error + Send + Sync> {
    Box::new(Message(format!("{where_}: {error}")))
}

fn canonical(value: &Value, depth: usize) -> Result<String, Box<dyn std::error::Error + Send + Sync>> {
    let pad = " ".repeat(INDENT * depth);

    Ok(match value {
        Value::Object(map) if map.is_empty() => format!("{pad}{{}}\n"),
        Value::Object(map) => {
            // A mapping has no order of its own, so sorting is what makes two
            // runs over the same structure produce the same bytes. serde_json's
            // Map is insertion-ordered without the preserve_order feature, so
            // the keys are collected and sorted rather than trusted.
            let mut names: Vec<&String> = map.keys().collect();
            names.sort();

            let mut out = String::new();
            for name in names {
                let item = &map[name];
                // The key is rendered before the branch, so neither arm needs a
                // fallible expression inside a closure.
                let key = scalar(&Value::String(name.clone()))
                    .map_err(|e| at(format!("at key {name:?}"), e))?;
                let rendered = if nested(item) {
                    canonical(item, depth + 1).map(|block| format!("{pad}{key}:\n{block}"))
                } else {
                    inline(item).map(|text| format!("{pad}{key}: {text}\n"))
                };
                out.push_str(&rendered.map_err(|e| at(format!("at key {name:?}"), e))?);
            }
            out
        }
        Value::Array(items) if items.is_empty() => format!("{pad}[]\n"),
        Value::Array(items) => {
            let mut out = String::new();
            for (index, item) in items.iter().enumerate() {
                let rendered = if nested(item) {
                    canonical(item, depth + 1).map(|block| {
                        let (first, rest) = block.split_once('\n').unwrap_or((block.as_str(), ""));
                        let mut piece = format!("{pad}- {}\n", first.trim_start());
                        if !rest.is_empty() {
                            piece.push_str(rest);
                            if !rest.ends_with('\n') {
                                piece.push('\n');
                            }
                        }
                        piece
                    })
                } else {
                    inline(item).map(|text| format!("{pad}- {text}\n"))
                };
                out.push_str(&rendered.map_err(|e| at(format!("at index {index}"), e))?);
            }
            out
        }
        other => format!("{pad}{}\n", inline(other)?),
    })
}

/// Whether a value renders as a block rather than on the key's own line.
/// A string, escaped the way YAML spells escapes. FR-4.9.
///
/// A raw control character in a quoted scalar is refused by a strict YAML reader
/// and folded to a space by a lenient one, so a file carrying one is read
/// differently depending on the reader. Escaping keeps every value writable,
/// which `docs/DECISIONS/parity-is-reached-by-widening-never-by-refusing.md`
/// requires.
///
/// U+0085, U+2028 and U+2029 are here because YAML 1.1 makes all three line
/// breaks and 1.2 does not, so which of them fold depends on the reader's
/// version rather than on the character. The table matches the Go pack byte for
/// byte, including uppercase hex.
fn escape(value: &str) -> String {
    let mut out = String::with_capacity(value.len());
    for ch in value.chars() {
        match ch {
            '\u{0}' => out.push_str("\\0"),
            '\u{7}' => out.push_str("\\a"),
            '\u{8}' => out.push_str("\\b"),
            '\t' => out.push_str("\\t"),
            '\n' => out.push_str("\\n"),
            '\u{b}' => out.push_str("\\v"),
            '\u{c}' => out.push_str("\\f"),
            '\r' => out.push_str("\\r"),
            '\u{1b}' => out.push_str("\\e"),
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\u{85}' => out.push_str("\\N"),
            '\u{2028}' => out.push_str("\\L"),
            '\u{2029}' => out.push_str("\\P"),
            '\u{feff}' => out.push_str("\\uFEFF"),
            c if (c < ' ') || c == '\u{7f}' || ('\u{80}'..='\u{9f}').contains(&c) => {
                out.push_str(&format!("\\x{:02X}", c as u32));
            }
            c => out.push(c),
        }
    }
    out
}

fn nested(value: &Value) -> bool {
    match value {
        Value::Object(map) => !map.is_empty(),
        Value::Array(items) => !items.is_empty(),
        _ => false,
    }
}

fn inline(value: &Value) -> Result<String, Box<dyn std::error::Error + Send + Sync>> {
    Ok(match value {
        Value::Object(_) => "{}".to_string(),
        Value::Array(_) => "[]".to_string(),
        other => scalar(other)?,
    })
}

fn scalar(value: &Value) -> Result<String, Box<dyn std::error::Error + Send + Sync>> {
    Ok(match value {
        Value::Null => "null".to_string(),
        Value::Bool(true) => "true".to_string(),
        Value::Bool(false) => "false".to_string(),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                i.to_string()
            } else if let Some(f) = n.as_f64() {
                // One spelling for every codec in every pack. FR-4.8.
                crate::float_text::canonical_float_text(f)
            } else {
                n.to_string()
            }
        }
        Value::String(s) => format!("\"{}\"", escape(s)),
        other => {
            return Err(Box::new(Message(format!(
                "cannot write {other} in canonical form"
            ))))
        }
    })
}
