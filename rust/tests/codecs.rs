//! The other two codecs, asserted against the same tables as the Go and Python
//! suites.
//!
//! A table that differs between packs is packs that differ, which is the whole
//! argument of `docs/PATTERNS/holding-two-packs-level.md`.

use std::cell::RefCell;

use serde_json::json;
use wrench::{
    load_json_file, save_json_file, save_toml_file, save_yaml_file, Codec, Reader, Writer, JSON,
    TOML,
};

struct Stub {
    data: Vec<u8>,
    written: RefCell<Option<Vec<u8>>>,
}

impl Stub {
    fn new(data: &[u8]) -> Self {
        Self {
            data: data.to_vec(),
            written: RefCell::new(None),
        }
    }
}

impl Reader for Stub {
    fn read(&self, _path: &str) -> Result<Vec<u8>, Box<dyn std::error::Error + Send + Sync>> {
        Ok(self.data.clone())
    }
}

impl Writer for Stub {
    fn write(
        &self,
        _path: &str,
        data: &[u8],
    ) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        *self.written.borrow_mut() = Some(data.to_vec());
        Ok(())
    }
}

const CANONICAL_JSON: &str =
    "{\n  \"a\": {\n    \"y\": \"x\",\n    \"z\": [\n      1,\n      2\n    ]\n  },\n  \"b\": 1,\n  \"d\": true\n}\n";

const CANONICAL_TOML: &str = "b = 1\nd = true\n\n[a]\ny = \"x\"\nz = [1, 2]\n";

fn three_formats() -> serde_json::Value {
    json!({"b": 1, "a": {"z": [1, 2], "y": "x"}, "d": true})
}

// COVERS: FR-2.7, FR-4.6 | property
#[test]
fn json_canonical_form() {
    let encoded = JSON.encode(&three_formats()).expect("encode");
    assert_eq!(String::from_utf8(encoded).unwrap(), CANONICAL_JSON);

    // Decoded and re-encoded, because a form nothing reads back is not a form.
    let value = JSON.decode(CANONICAL_JSON.as_bytes()).expect("decode");
    let again = JSON.encode(&value).expect("re-encode");
    assert_eq!(
        String::from_utf8(again).unwrap(),
        CANONICAL_JSON,
        "not a fixed point"
    );
}

// COVERS: FR-2.7, FR-4.7 | property
#[test]
fn toml_canonical_form() {
    let encoded = TOML.encode(&three_formats()).expect("encode");
    assert_eq!(String::from_utf8(encoded).unwrap(), CANONICAL_TOML);

    let value = TOML.decode(CANONICAL_TOML.as_bytes()).expect("decode");
    let again = TOML.encode(&value).expect("re-encode");
    assert_eq!(
        String::from_utf8(again).unwrap(),
        CANONICAL_TOML,
        "not a fixed point"
    );
}

// COVERS: FR-4.7 | edge
#[test]
fn toml_writes_an_array_of_tables_as_repeated_sections() {
    // The most ordinary shape in a hand-written config, and the one TOML has no
    // inline spelling for. Found by the skid session round-tripping a real
    // config while FR-4.7 was still being written: the emitter sent every array
    // down the inline path, so [[x]] had no route at all.
    let value = json!({
        "name": "x",
        "substitution": [
            {"kind": "literal", "pattern": "kokoro"},
            {"kind": "regex", "pattern": "skid"},
        ],
    });
    let want = "name = \"x\"\n\n[[substitution]]\nkind = \"literal\"\npattern = \"kokoro\"\n\
                \n[[substitution]]\nkind = \"regex\"\npattern = \"skid\"\n";

    let encoded = TOML.encode(&value).expect("encode");
    assert_eq!(String::from_utf8(encoded).unwrap(), want);

    // An empty array is not a table array, whatever it would have held.
    let empty = TOML.encode(&json!({"a": []})).expect("encode empty");
    assert_eq!(String::from_utf8(empty).unwrap(), "a = []\n");
}

// COVERS: FR-4.7 | negative
#[test]
fn toml_refuses_a_null() {
    let err = TOML
        .encode(&json!({"a": {"b": null}}))
        .expect_err("a null was accepted");
    assert!(
        err.to_string().contains("a.b"),
        "the error does not say where: {err}"
    );
}

// COVERS: FR-4.7 | edge
#[test]
fn toml_refuses_a_document_that_is_not_a_table() {
    TOML.encode(&json!([1, 2]))
        .expect_err("a top-level array was accepted");
}

// COVERS: FR-4.7 | regression
#[test]
fn toml_temporal_types_decode_to_iso_strings() {
    let value = TOML
        .decode(b"d = 2026-01-01\ndt = 2026-01-01T07:32:00Z\n")
        .expect("decode");
    assert_eq!(value["d"], json!("2026-01-01"));
    assert!(
        value["dt"].as_str().unwrap().starts_with("2026-01-01T07:32:00"),
        "an offset datetime became {}",
        value["dt"]
    );
}

// COVERS: FR-2.10 | positive
#[test]
fn a_wrapper_per_format_supplies_the_codec() {
    let writer = Stub::new(b"");
    save_json_file(
        &json!({"success": true}),
        "out.json",
        &wrench::ENVELOPE_SCHEMA,
        &writer,
    )
    .expect("save json");
    assert_eq!(
        writer.written.borrow().clone().unwrap(),
        b"{\n  \"success\": true\n}\n".to_vec()
    );

    let reader = Stub::new(br#"{"success": true}"#);
    let value =
        load_json_file("out.json", &wrench::ENVELOPE_SCHEMA, &reader).expect("load json");
    assert_eq!(value["success"], json!(true));

    let toml_writer = Stub::new(b"");
    save_toml_file(
        &json!({"success": true}),
        "out.toml",
        &wrench::ENVELOPE_SCHEMA,
        &toml_writer,
    )
    .expect("save toml");
    assert_eq!(
        toml_writer.written.borrow().clone().unwrap(),
        b"success = true\n".to_vec()
    );

    let yaml_writer = Stub::new(b"");
    save_yaml_file(
        &json!({"success": true}),
        "out.yaml",
        &wrench::ENVELOPE_SCHEMA,
        &yaml_writer,
    )
    .expect("save yaml");
    assert_eq!(
        yaml_writer.written.borrow().clone().unwrap(),
        b"\"success\": true\n".to_vec()
    );
}

// COVERS: FR-2.10 | negative
#[test]
fn a_wrapper_still_validates() {
    let writer = Stub::new(b"");
    save_json_file(
        &json!({"success": "yes"}),
        "out.json",
        &wrench::ENVELOPE_SCHEMA,
        &writer,
    )
    .expect_err("the wrapper accepted a structure the schema refuses");
    assert!(
        writer.written.borrow().is_none(),
        "the writer ran despite validation failing"
    );
}
