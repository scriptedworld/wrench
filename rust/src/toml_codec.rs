//! The TOML codec: bytes to a structure, and a structure to canonical bytes.
//!
//! TOML is the one format wrench ships that cannot hold everything the other
//! two can, so two questions were answered rather than implemented around, and
//! both are answered the way the contract answers them elsewhere.
//!
//! A null is refused rather than substituted. TOML has no null, and FR-4.1 says
//! a value with no canonical form is refused rather than guessed at.
//!
//! A date decodes to its ISO 8601 string, which is what FR-2.9 requires of every
//! decoder. A TOML datetime carries which of the four temporal types it was, and
//! each is spelled the way Python's `tomllib` plus `.isoformat()` spells it, so
//! the packs agree about the same file.
//!
//! A TOML document is a table. There is no top-level scalar or array in the
//! format, so encoding one is refused rather than wrapped in an invented key.
//!
//! THE EMITTER IS WRITTEN BY HAND, for the reason the YAML emitter is: no TOML
//! library produces these bytes. Measured 2026-08-28, the same structure through
//! three libraries differed in array layout and in indentation under a table.

use serde_json::{Map, Value};

use crate::codec::Codec;

/// The TOML codec.
pub struct TomlCodec;

/// The one instance callers use.
pub const TOML: TomlCodec = TomlCodec;

type Fail = Box<dyn std::error::Error + Send + Sync>;

impl Codec for TomlCodec {
    fn decode(&self, data: &[u8]) -> Result<Value, Fail> {
        let text = std::str::from_utf8(data)?;
        let parsed: toml::Value = toml::from_str(text)?;
        Ok(from_toml(&parsed))
    }

    fn encode(&self, value: &Value) -> Result<Vec<u8>, Fail> {
        let table = value
            .as_object()
            .ok_or("cannot write in canonical form: a TOML document is a table")?;
        refuse_null(value, "")?;

        let mut out = String::new();
        write_table(&mut out, table, &[])?;
        Ok(out.into_bytes())
    }
}

/// A `toml::Value` as the maps, lists and JSON scalars FR-2.9 requires.
fn from_toml(value: &toml::Value) -> Value {
    match value {
        toml::Value::String(s) => Value::String(s.clone()),
        toml::Value::Integer(i) => Value::from(*i),
        toml::Value::Float(f) => Value::from(*f),
        toml::Value::Boolean(b) => Value::Bool(*b),
        // A datetime keeps which of the four types it was. `toml`'s Display
        // spells each one the way `tomllib` plus `.isoformat()` does, so the
        // packs agree without a format string per case.
        toml::Value::Datetime(d) => Value::String(d.to_string()),
        toml::Value::Array(items) => Value::Array(items.iter().map(from_toml).collect()),
        toml::Value::Table(table) => {
            let mut out = Map::new();
            for (name, item) in table {
                out.insert(name.clone(), from_toml(item));
            }
            Value::Object(out)
        }
    }
}

/// Refuse a null anywhere in the structure, naming where it sits.
fn refuse_null(value: &Value, where_: &str) -> Result<(), Fail> {
    match value {
        Value::Null => {
            let at = if where_.is_empty() {
                String::new()
            } else {
                format!(" at {where_}")
            };
            Err(format!("cannot write null in canonical form{at}: TOML has no null").into())
        }
        Value::Object(table) => {
            for (name, item) in table {
                let path = if where_.is_empty() {
                    name.clone()
                } else {
                    format!("{where_}.{name}")
                };
                refuse_null(item, &path)?;
            }
            Ok(())
        }
        Value::Array(items) => {
            for (index, item) in items.iter().enumerate() {
                refuse_null(item, &format!("{where_}[{index}]"))?;
            }
            Ok(())
        }
        _ => Ok(()),
    }
}

/// One table: its scalars, then its sub-tables, each sorted.
///
/// Scalars first because TOML binds a bare key to the most recent `[header]`, so
/// a scalar written after a sub-table would land inside it. That is a
/// correctness rule rather than a layout preference.
///
/// `serde_json`'s map is a `BTreeMap` here, because `preserve_order` is
/// deliberately not enabled, so iteration is already sorted.
fn write_table(out: &mut String, value: &Map<String, Value>, path: &[&str]) -> Result<(), Fail> {
    if !path.is_empty() {
        let parts: Vec<String> = path.iter().map(|part| key(part)).collect();
        out.push_str(&format!("[{}]\n", parts.join(".")));
    }

    let mut sections = Vec::new();
    for (name, item) in value {
        if item.is_object() || is_table_array(item) {
            sections.push(name);
            continue;
        }
        out.push_str(&format!("{} = {}\n", key(name), inline(item)?));
    }

    for name in sections {
        let mut deeper: Vec<&str> = path.to_vec();
        deeper.push(name);

        if let Some(table) = value[name].as_object() {
            out.push('\n');
            write_table(out, table, &deeper)?;
            continue;
        }
        // An array of tables is repeated `[[path]]` sections. TOML has no inline
        // form for one, so this is the only spelling available rather than a
        // choice between two.
        let parts: Vec<String> = deeper.iter().map(|part| key(part)).collect();
        let header = parts.join(".");
        for entry in value[name].as_array().expect("a table array is an array") {
            out.push_str(&format!("\n[[{header}]]\n"));
            write_table(out, entry.as_object().expect("a table array holds tables"), &[])?;
        }
    }
    Ok(())
}

/// A non-empty array whose every item is a table.
///
/// Empty stays inline as `[]`, because an empty array of tables and an empty
/// array of anything else are the same document and `[]` is the shorter of the
/// two spellings. A mixed array is not a table array and is refused by `inline`,
/// which is where the message about it belongs.
fn is_table_array(value: &Value) -> bool {
    match value.as_array() {
        Some(items) => !items.is_empty() && items.iter().all(Value::is_object),
        None => false,
    }
}

/// A key, bare where TOML allows it and quoted where it does not.
fn key(name: &str) -> String {
    if !name.is_empty()
        && name
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-')
    {
        name.to_string()
    } else {
        string(name)
    }
}

/// A value on one line: a scalar, or an array of them.
fn inline(value: &Value) -> Result<String, Fail> {
    Ok(match value {
        Value::Bool(true) => "true".to_string(),
        Value::Bool(false) => "false".to_string(),
        Value::String(s) => string(s),
        Value::Number(n) => number(n),
        Value::Array(items) => {
            let parts: Result<Vec<String>, Fail> = items.iter().map(inline).collect();
            format!("[{}]", parts?.join(", "))
        }
        // An inline table would be a second way to spell a sub-table, and two
        // spellings of one thing is what canonical form exists to remove.
        Value::Object(_) => return Err("cannot write a table inline in canonical form".into()),
        Value::Null => return Err("cannot write null in canonical form".into()),
    })
}

/// A number, with a whole float keeping its decimal point, in step with the YAML
/// codec: a float that reads back as an integer is the same defect either way.
fn number(n: &serde_json::Number) -> String {
    if let Some(i) = n.as_i64() {
        return i.to_string();
    }
    if let Some(f) = n.as_f64() {
        let text = format!("{f}");
        if text.contains('.') || text.contains('e') || text.contains('E') {
            return text;
        }
        return format!("{text}.0");
    }
    n.to_string()
}

/// A basic string, escaped the way TOML spells escapes.
fn string(value: &str) -> String {
    let escaped = value
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\t', "\\t")
        .replace('\r', "\\r");
    format!("\"{escaped}\"")
}
