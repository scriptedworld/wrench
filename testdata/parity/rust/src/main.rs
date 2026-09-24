//! The Rust pack's parity driver: encode the shared tree, decode a file.
//!
//! Called by `bin/test-cross-pack-parity.py`, which owns the wire format this
//! reads and writes. Two subcommands, the same two in every pack's driver:
//!
//! ```text
//! wrench-parity-driver encode <yaml|json> <probe-in.json> <out-path>
//! wrench-parity-driver decode <yaml|json> <in-path> <probe-out.json>
//! ```
//!
//! It calls the pack's public API and nothing else. A driver that repaired,
//! rounded or reordered anything would hide the divergence the checker exists
//! to find, so the tagged wire carries what `serde_json::Value` actually holds:
//! an integer that fits a 64-bit type is reported as one, and a number held as
//! a double is reported by its bits.

use std::fs;
use std::process::ExitCode;

use serde_json::{Map, Number, Value};
use wrench::{
    compile_schema, load_formatted_file, save_formatted_file, Codec, JSON, LOCAL_FILE, YAML,
};

const WIRE: i64 = 1;

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn unhex(text: &str) -> Result<Vec<u8>, String> {
    if !text.len().is_multiple_of(2) {
        return Err(format!("odd-length hex string {text:?}"));
    }
    (0..text.len())
        .step_by(2)
        .map(|at| u8::from_str_radix(&text[at..at + 2], 16).map_err(|e| e.to_string()))
        .collect()
}

fn tagged(kind: &str, value: Value) -> Value {
    let mut node = Map::new();
    node.insert("k".to_string(), Value::String(kind.to_string()));
    node.insert("v".to_string(), value);
    Value::Object(node)
}

fn to_wire(value: &Value) -> Value {
    match value {
        Value::Null => {
            let mut node = Map::new();
            node.insert("k".to_string(), Value::String("null".to_string()));
            Value::Object(node)
        }
        Value::Bool(flag) => tagged("bool", Value::String(flag.to_string())),
        Value::String(text) => tagged("str", Value::String(hex(text.as_bytes()))),
        Value::Number(number) => number_to_wire(number),
        Value::Array(items) => tagged("seq", Value::Array(items.iter().map(to_wire).collect())),
        Value::Object(entries) => tagged(
            "map",
            Value::Array(
                entries
                    .iter()
                    .map(|(key, item)| {
                        Value::Array(vec![Value::String(hex(key.as_bytes())), to_wire(item)])
                    })
                    .collect(),
            ),
        ),
    }
}

fn number_to_wire(number: &Number) -> Value {
    if let Some(whole) = number.as_i64() {
        return tagged("int", Value::String(whole.to_string()));
    }
    if let Some(unsigned) = number.as_u64() {
        return tagged("int", Value::String(unsigned.to_string()));
    }
    match number.as_f64() {
        Some(real) => tagged("float", Value::String(format!("{:016x}", real.to_bits()))),
        None => tagged("foreign", Value::String(format!("Number: {number}"))),
    }
}

fn from_wire(node: &Value) -> Result<Value, String> {
    let kind = node
        .get("k")
        .and_then(Value::as_str)
        .ok_or_else(|| format!("wire node with no kind: {node}"))?;
    match kind {
        "null" => Ok(Value::Null),
        "bool" => Ok(Value::Bool(text_of(node)? == "true")),
        "int" => from_wire_int(text_of(node)?),
        "float" => from_wire_float(text_of(node)?),
        "str" => Ok(Value::String(
            String::from_utf8(unhex(text_of(node)?)?).map_err(|e| e.to_string())?,
        )),
        "seq" => from_wire_seq(node),
        "map" => from_wire_map(node),
        other => Err(format!("unknown wire node kind {other:?}")),
    }
}

fn text_of(node: &Value) -> Result<&str, String> {
    node.get("v")
        .and_then(Value::as_str)
        .ok_or_else(|| format!("wire node with no string value: {node}"))
}

fn from_wire_int(text: &str) -> Result<Value, String> {
    if let Ok(whole) = text.parse::<i64>() {
        return Ok(Value::Number(Number::from(whole)));
    }
    if let Ok(unsigned) = text.parse::<u64>() {
        return Ok(Value::Number(Number::from(unsigned)));
    }
    Err(format!(
        "integer {text} does not fit 64 bits, which this pack has no type for"
    ))
}

fn from_wire_float(text: &str) -> Result<Value, String> {
    let pattern = u64::from_str_radix(text, 16).map_err(|e| e.to_string())?;
    Number::from_f64(f64::from_bits(pattern))
        .map(Value::Number)
        .ok_or_else(|| format!("{text} is not a finite double"))
}

fn from_wire_seq(node: &Value) -> Result<Value, String> {
    let items = node
        .get("v")
        .and_then(Value::as_array)
        .ok_or_else(|| format!("sequence node with no items: {node}"))?;
    items
        .iter()
        .map(from_wire)
        .collect::<Result<Vec<_>, _>>()
        .map(Value::Array)
}

fn from_wire_map(node: &Value) -> Result<Value, String> {
    let pairs = node
        .get("v")
        .and_then(Value::as_array)
        .ok_or_else(|| format!("map node with no pairs: {node}"))?;
    let mut built = Map::new();
    for pair in pairs {
        let both = pair
            .as_array()
            .ok_or_else(|| format!("map entry that is not a pair: {pair}"))?;
        let key = both
            .first()
            .and_then(Value::as_str)
            .ok_or_else(|| format!("map entry with no key: {pair}"))?;
        let name = String::from_utf8(unhex(key)?).map_err(|e| e.to_string())?;
        let item = both
            .get(1)
            .ok_or_else(|| format!("map entry with no value: {pair}"))?;
        built.insert(name, from_wire(item)?);
    }
    Ok(Value::Object(built))
}

fn codec(format: &str) -> Result<&'static dyn Codec, String> {
    match format {
        "yaml" => Ok(&YAML),
        "json" => Ok(&JSON),
        other => Err(format!("unknown format {other:?}")),
    }
}

fn encode(format: &str, probe_path: &str, out_path: &str) -> Result<(), String> {
    let raw = fs::read_to_string(probe_path).map_err(|e| e.to_string())?;
    let carried: Value = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
    if carried.get("wire").and_then(Value::as_i64) != Some(WIRE) {
        return Err(format!("wire version is not {WIRE}"));
    }
    let value = from_wire(
        carried
            .get("value")
            .ok_or_else(|| "the probe carries no value".to_string())?,
    )?;
    // Anything is a valid instance, so the parity tree is judged by the codecs
    // and not by a schema. The schema argument cannot be omitted (FR-2.2), so
    // the permissive one is what a driver hands it.
    let schema = compile_schema("wrench-parity-driver", "{}").map_err(|e| e.to_string())?;
    save_formatted_file(
        &value,
        out_path,
        schema.as_ref(),
        codec(format)?,
        &LOCAL_FILE,
    )
    .map_err(|e| e.to_string())
}

fn decode(format: &str, in_path: &str, probe_path: &str) -> Result<(), String> {
    let schema = compile_schema("wrench-parity-driver", "{}").map_err(|e| e.to_string())?;
    let value = load_formatted_file(in_path, schema.as_ref(), codec(format)?, &LOCAL_FILE)
        .map_err(|e| e.to_string())?;
    let mut envelope = Map::new();
    envelope.insert("wire".to_string(), Value::Number(Number::from(WIRE)));
    envelope.insert("value".to_string(), to_wire(&value));
    fs::write(probe_path, Value::Object(envelope).to_string()).map_err(|e| e.to_string())
}

fn run(args: &[String]) -> Result<(), String> {
    match args {
        [action, format, source, target] if action == "encode" => encode(format, source, target),
        [action, format, source, target] if action == "decode" => decode(format, source, target),
        _ => Err("usage: wrench-parity-driver encode|decode yaml|json <in> <out>".to_string()),
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match run(&args) {
        Ok(()) => ExitCode::SUCCESS,
        Err(why) => {
            eprintln!("{why}");
            ExitCode::FAILURE
        }
    }
}
