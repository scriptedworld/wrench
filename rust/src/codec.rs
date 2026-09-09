//! The YAML codec: bytes to a value, and a value to canonical bytes.
//!
//! Canonical form is block style, one key to a line, keys sorted, and a scalar
//! quoted exactly when it is meant to be a string. Booleans and numbers stay
//! bare. Quoting marks intent, so `no`, `1.20` and `null` survive a round trip
//! as the strings they were.
//!
//! libyaml EMITS. The document is handed to it as events with the style named
//! on each scalar, and it decides layout, indentation, escaping and line
//! breaks. Its escape table is already the one this pack wants. What is here
//! is the four adapters and nothing that produces text.
//!
//! yaml-rust2 parses; its emitter cannot be used, and Cargo.toml says why.

use libyaml_safer::{Emitter, Encoding, Event, MappingStyle, ScalarStyle, SequenceStyle};
use serde_json::{Map, Value};
use yaml_rust2::{yaml::Yaml, YamlLoader};

use crate::errors::Message;

const INDENT: usize = 2;

/// A format, knowing nothing about where the bytes came from.
pub trait Codec {
    fn decode(&self, data: &[u8]) -> Result<Value, crate::Error>;
    fn encode(&self, value: &Value) -> Result<Vec<u8>, crate::Error>;
}

/// The YAML codec that ships.
pub struct YamlCodec;

/// The one instance callers use.
pub const YAML: YamlCodec = YamlCodec;

impl Codec for YamlCodec {
    fn decode(&self, data: &[u8]) -> Result<Value, crate::Error> {
        let text = std::str::from_utf8(data).map_err(crate::Error::parse)?;
        let documents = YamlLoader::load_from_str(text).map_err(crate::Error::parse)?;
        match documents.len() {
            0 => Ok(Value::Null),
            1 => Ok(normalise(&documents[0])?),
            n => Err(crate::Error::parse(Message(format!(
                "{n} documents in one file, want exactly one"
            )))),
        }
    }

    fn encode(&self, value: &Value) -> Result<Vec<u8>, crate::Error> {
        canonical(value)
    }
}

/// What the parser produced, in the shape a JSON Schema validator expects.
///
/// FR-2.9: maps, lists and JSON scalars, and nothing else. A mapping key that is
/// not a string has no JSON equivalent and is refused rather than coerced,
/// because coercing invents a document nobody wrote.
fn normalise(node: &Yaml) -> Result<Value, crate::Error> {
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
                    crate::Error::parse(Message(format!("mapping key {key:?} is not a string")))
                })?;
                out.insert(name.to_string(), normalise(item)?);
            }
            Value::Object(out)
        }
        Yaml::Alias(_) => {
            return Err(crate::Error::parse(Message(
                "an alias has no JSON equivalent and is refused rather than expanded".to_string(),
            )))
        }
    })
}

/// A YAML real, refused where JSON has no way to say it.
fn real(text: &str) -> Result<Value, crate::Error> {
    let parsed: f64 = text.parse().map_err(crate::Error::parse)?;
    // NaN and the infinities are refused: YAML can spell them and JSON Schema
    // cannot represent them, so a file carrying one is a file no consumer in
    // this ecosystem can validate.
    serde_json::Number::from_f64(parsed)
        .map(Value::Number)
        .ok_or_else(|| {
            crate::Error::parse(Message(format!(
                "cannot represent {text} in canonical form"
            )))
        })
}

/// Where in the structure a failure happened, so a caller can find the value.
/// The Go and Python packs word it identically; a message that differs by pack
/// is one a consumer cannot be told to look for.
fn at(where_: String, error: crate::Error) -> crate::Error {
    crate::Error::encode(Message(format!("{where_}: {error}")))
}

/// A plain scalar: the spelling is the value's own and needs no quotes.
fn plain(text: &str) -> Event {
    Event::scalar(None, None, text, true, false, ScalarStyle::Plain)
}

/// A double-quoted scalar. ADAPTER 2, and libyaml escapes the contents.
fn quoted(text: &str) -> Event {
    Event::scalar(None, None, text, false, true, ScalarStyle::DoubleQuoted)
}

/// Feed one value to the emitter as events.
///
/// This produces no text. Every branch hands libyaml a node and a style, and
/// libyaml decides layout, indentation, escaping and line breaks.
fn walk(emitter: &mut Emitter, value: &Value) -> Result<(), crate::Error> {
    match value {
        Value::Null => emit_one(emitter, plain("null")),
        Value::Bool(flag) => emit_one(emitter, plain(if *flag { "true" } else { "false" })),
        Value::String(text) => emit_one(emitter, quoted(text)),
        Value::Number(number) => {
            // ADAPTER 3. An integer is its own spelling; a float is FR-4.8's,
            // which is positional decimal and never an exponent.
            let text = match number.as_i64() {
                Some(whole) => whole.to_string(),
                None => match number.as_f64() {
                    Some(real) => crate::float_text::canonical_float_text(real),
                    None => number.to_string(),
                },
            };
            emit_one(emitter, plain(&text))
        }
        Value::Array(items) => {
            emit_one(
                emitter,
                Event::sequence_start(None, None, true, SequenceStyle::Block),
            )?;
            for (index, item) in items.iter().enumerate() {
                walk(emitter, item).map_err(|e| at(format!("at index {index}"), e))?;
            }
            emit_one(emitter, Event::sequence_end())
        }
        Value::Object(map) => {
            emit_one(
                emitter,
                Event::mapping_start(None, None, true, MappingStyle::Block),
            )?;
            // ADAPTER 1. A mapping has no order of its own, and serde_json's Map
            // is insertion-ordered, so the keys are sorted rather than trusted.
            let mut names: Vec<&String> = map.keys().collect();
            names.sort();
            for name in names {
                emit_one(emitter, quoted(name))?;
                walk(emitter, &map[name]).map_err(|e| at(format!("at key {name:?}"), e))?;
            }
            emit_one(emitter, Event::mapping_end())
        }
    }
}

fn emit_one(emitter: &mut Emitter, event: Event) -> Result<(), crate::Error> {
    emitter
        .emit(event)
        .map_err(|e| crate::Error::encode(Message(e.to_string())))
}

/// The whole document, emitted by libyaml.
fn canonical(value: &Value) -> Result<Vec<u8>, crate::Error> {
    let mut out: Vec<u8> = Vec::new();
    {
        let mut emitter = Emitter::new();
        emitter.set_output_string(&mut out);
        // Settings rather than code. Width off because the default folds a long
        // scalar across lines, which reads back the same and makes a diff
        // noisy; unicode on so a non-ASCII character is written as itself.
        emitter.set_width(-1);
        emitter.set_unicode(true);
        emitter.set_indent(INDENT as i32);

        emit_one(&mut emitter, Event::stream_start(Encoding::Utf8))?;
        // Implicit, so there is no `---` line.
        emit_one(&mut emitter, Event::document_start(None, &[], true))?;
        walk(&mut emitter, value)?;
        emit_one(&mut emitter, Event::document_end(true))?;
        emit_one(&mut emitter, Event::stream_end())?;
    }
    Ok(out)
}
