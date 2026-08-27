//! Tests for the Rust pack.
//!
//! The canonical cases come from `testdata/canonical/`, the same directories the
//! Go and Python packs are held to. That is the point of them: implementations
//! agreeing on the schema and disagreeing on the bytes is the failure a shared
//! fixture set exists to catch, and no pack is the oracle for another.

use std::cell::RefCell;
use std::fs;
use std::path::PathBuf;

use serde_json::{json, Value};
use wrench::{
    compile_schema, load_formatted_file, save_formatted_file, Codec, Reader, Schema, Writer, YAML,
};

fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("rust/ has a parent")
        .to_path_buf()
}

fn fixtures() -> Vec<String> {
    let mut names: Vec<String> = fs::read_dir(root().join("testdata/canonical"))
        .expect("the fixture set is readable")
        .filter_map(|e| e.ok())
        .filter(|e| e.path().is_dir())
        .map(|e| e.file_name().to_string_lossy().to_string())
        .collect();
    names.sort();
    assert!(!names.is_empty(), "the fixture set holds no cases");
    names
}

/// Bytes without a filesystem. Its existence is the point of FR-2.5a: a reader
/// takes the path, so a test replaces the whole IO boundary.
struct Stub {
    data: Vec<u8>,
    fail: bool,
    saw_path: RefCell<Option<String>>,
    written: RefCell<Option<Vec<u8>>>,
}

impl Stub {
    fn new(data: &[u8]) -> Self {
        Self {
            data: data.to_vec(),
            fail: false,
            saw_path: RefCell::new(None),
            written: RefCell::new(None),
        }
    }

    fn failing() -> Self {
        Self {
            data: Vec::new(),
            fail: true,
            saw_path: RefCell::new(None),
            written: RefCell::new(None),
        }
    }
}

impl Reader for Stub {
    fn read(&self, path: &str) -> Result<Vec<u8>, Box<dyn std::error::Error + Send + Sync>> {
        *self.saw_path.borrow_mut() = Some(path.to_string());
        if self.fail {
            return Err("no such file".into());
        }
        Ok(self.data.clone())
    }
}

impl Writer for Stub {
    fn write(&self, path: &str, data: &[u8]) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        *self.saw_path.borrow_mut() = Some(path.to_string());
        if self.fail {
            return Err("cannot write".into());
        }
        *self.written.borrow_mut() = Some(data.to_vec());
        Ok(())
    }
}

fn anything() -> Box<dyn Schema> {
    compile_schema(
        "anything.schema.json",
        r#"{"$schema": "https://json-schema.org/draft/2020-12/schema"}"#,
    )
    .expect("a permissive schema compiles")
}

// COVERS: FR-4.1, FR-4.2, FR-4.3, FR-4.4, FR-5.5, FR-5.6 | property
#[test]
fn canonical_form_matches_the_shared_fixtures() {
    for case in fixtures() {
        let dir = root().join("testdata/canonical").join(&case);
        let input = fs::read(dir.join("input.yaml")).expect("an input");
        let want = fs::read_to_string(dir.join("canonical.yaml")).expect("a golden");

        let value = YAML.decode(&input).unwrap_or_else(|e| panic!("{case}: decoding: {e}"));
        let got = YAML.encode(&value).unwrap_or_else(|e| panic!("{case}: encoding: {e}"));

        assert_eq!(
            String::from_utf8_lossy(&got),
            want,
            "{case}: canonical form differs from the shared fixture"
        );

        // A fixture that is an instance of a shipped schema says so, and is held
        // to it. Byte-identical output says two packs agree on the spelling, not
        // that the thing they spelled is a document a consumer would accept.
        if let Ok(id) = fs::read_to_string(dir.join("schema")) {
            let schema = shipped_by_id(id.trim());
            schema
                .validate(&value)
                .unwrap_or_else(|e| panic!("{case}: does not satisfy the schema it declares: {e}"));
        }
    }
}

fn shipped_by_id(id: &str) -> &'static dyn Schema {
    match id {
        "https://scriptedworld.github.io/wrench/envelope.schema.json" => &wrench::ENVELOPE_SCHEMA,
        "https://scriptedworld.github.io/wrench/jig.schema.json" => &wrench::JIG_SCHEMA,
        "https://scriptedworld.github.io/wrench/manifest.schema.json" => &wrench::MANIFEST_SCHEMA,
        "https://scriptedworld.github.io/wrench/definitions.schema.json" => {
            &wrench::DEFINITIONS_SCHEMA
        }
        other => panic!("a fixture declares {other}, which this pack does not ship"),
    }
}

// COVERS: FR-4.5 | property
#[test]
fn canonical_form_is_a_fixed_point() {
    for case in fixtures() {
        let canonical = fs::read(
            root()
                .join("testdata/canonical")
                .join(&case)
                .join("canonical.yaml"),
        )
        .expect("a golden");
        let again = YAML
            .encode(&YAML.decode(&canonical).expect("decodes"))
            .expect("encodes");
        assert_eq!(
            String::from_utf8_lossy(&again),
            String::from_utf8_lossy(&canonical),
            "{case}: encoding the canonical form changed it"
        );
    }
}

// COVERS: FR-3.8 | positive
#[test]
fn every_shipped_schema_has_an_instance_fixture() {
    let mut seen: Vec<String> = Vec::new();
    for case in fixtures() {
        let path = root().join("testdata/canonical").join(&case).join("schema");
        if let Ok(id) = fs::read_to_string(&path) {
            seen.push(id.trim().to_string());
        }
    }
    for id in wrench::shipped_ids() {
        assert!(
            seen.iter().any(|s| s == id),
            "no fixture is an instance of {id}, so nothing validates against it"
        );
    }
}

// COVERS: FR-2.1, FR-2.2 | positive
#[test]
fn load_returns_the_validated_structure() {
    let value = load_formatted_file(
        "output.yaml",
        &wrench::ENVELOPE_SCHEMA,
        &YAML,
        &Stub::new(b"success: true\n"),
    )
    .expect("a valid envelope loads");
    assert_eq!(value, json!({"success": true}));
}

// COVERS: FR-2.5a | positive
#[test]
fn the_reader_is_handed_the_path() {
    let reader = Stub::new(b"success: true\n");
    let _ = load_formatted_file("nowhere/output.yaml", &wrench::ENVELOPE_SCHEMA, &YAML, &reader);
    assert_eq!(
        reader.saw_path.borrow().as_deref(),
        Some("nowhere/output.yaml")
    );
}

// COVERS: FR-2.6 | negative
#[test]
fn a_failure_says_which_step_failed() {
    let read = load_formatted_file("gone.yaml", &wrench::ENVELOPE_SCHEMA, &YAML, &Stub::failing())
        .expect_err("a failing reader fails the call");
    assert_eq!(read.step(), "read");

    let parse = load_formatted_file(
        "f.yaml",
        &wrench::ENVELOPE_SCHEMA,
        &YAML,
        &Stub::new(b"success: [unterminated\n"),
    )
    .expect_err("unparseable bytes fail the call");
    assert_eq!(parse.step(), "parse");

    let validate = load_formatted_file(
        "f.yaml",
        &wrench::ENVELOPE_SCHEMA,
        &YAML,
        &Stub::new(b"success: \"yes\"\n"),
    )
    .expect_err("a wrong type fails the call");
    assert_eq!(validate.step(), "validate");

    // bolt's FR-6.11 needs parse and validate distinguishable from each other
    // and from read, to say which of three things an adapter did wrong.
    assert_ne!(parse.step(), validate.step());
}

// COVERS: FR-2.4 | negative
#[test]
fn save_refuses_a_structure_it_would_not_read_back() {
    let writer = Stub::new(b"");
    let error = save_formatted_file(
        &json!({"success": "yes"}),
        "f.yaml",
        &wrench::ENVELOPE_SCHEMA,
        &YAML,
        &writer,
    )
    .expect_err("an invalid envelope is refused");
    assert_eq!(error.step(), "validate");
    assert!(
        writer.written.borrow().is_none(),
        "the writer ran despite validation failing"
    );
}

// COVERS: FR-4.3 | positive
#[test]
fn save_writes_canonical_form() {
    let writer = Stub::new(b"");
    save_formatted_file(
        &json!({"success": false, "reasons": [{"kind": "k", "message": "m"}]}),
        "f.yaml",
        &wrench::ENVELOPE_SCHEMA,
        &YAML,
        &writer,
    )
    .expect("a valid envelope saves");

    let written = writer.written.borrow().clone().expect("bytes were written");
    assert_eq!(
        String::from_utf8_lossy(&written),
        "\"reasons\":\n  - \"kind\": \"k\"\n    \"message\": \"m\"\n\"success\": false\n"
    );
}

// COVERS: FR-3.1, FR-3.3, FR-3.6 | positive
#[test]
fn a_jigs_definitions_block_is_held_to_the_shared_shape() {
    let flat = b"definitions:\n  requirements: REQUIREMENTS.md\n  line_length: 100\ntasks:\n  - name: check\n    command: \"true\"\n";
    load_formatted_file("bolt.q.yaml", &wrench::JIG_SCHEMA, &YAML, &Stub::new(flat))
        .expect("a flat definitions block is accepted");

    let nested = b"definitions:\n  python:\n    line_length: 100\ntasks:\n  - name: check\n    command: \"true\"\n";
    load_formatted_file("bolt.q.yaml", &wrench::JIG_SCHEMA, &YAML, &Stub::new(nested))
        .expect_err("a nested value is refused, so the reference resolved");
}

// COVERS: FR-3.10 | positive
#[test]
fn a_consumer_schema_may_reference_a_shipped_one() {
    let schema = compile_schema(
        "mine.schema.json",
        r#"{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object",
            "properties":{"d":{"$ref":"https://scriptedworld.github.io/wrench/definitions.schema.json"}}}"#,
    )
    .expect("a schema referencing a shipped one compiles");

    schema
        .validate(&json!({"d": {"a": "x"}}))
        .expect("a flat definitions mapping is accepted");
    schema
        .validate(&json!({"d": {"a": {"b": 1}}}))
        .expect_err("a nested value is refused, so the reference resolved");
}

// COVERS: FR-3.10 | negative
#[test]
fn a_schema_may_reference_nothing_outside_the_shipped_set() {
    // This pack gets FR-3.10 at compile time: jsonschema is declared without
    // resolve-file and resolve-http, so there is no code that could fetch.
    for target in [
        "file:///tmp/local.schema.json",
        "/tmp/local.schema.json",
        "local.schema.json",
        "https://example.com/x.schema.json",
        "https://scriptedworld.github.io/wrench/not-shipped.schema.json",
    ] {
        let document = format!(
            r#"{{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object","properties":{{"d":{{"$ref":"{target}"}}}}}}"#
        );
        assert!(
            compile_schema("mine.schema.json", &document).is_err(),
            "{target} resolved, so validation depends on something outside the process"
        );
    }
}

// COVERS: FR-3.10 | edge
#[test]
fn a_caller_cannot_redefine_a_shipped_schema() {
    for id in wrench::shipped_ids() {
        assert!(
            compile_schema(
                id,
                r#"{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"string"}"#
            )
            .is_err(),
            "{id} was redefined by a caller"
        );
    }
}

// COVERS: FR-2.9 | regression
#[test]
fn a_timestamp_decodes_to_a_string_so_it_can_be_written_back() {
    let value = YAML
        .decode(b"day: 2026-01-01\nstamp: 2026-01-01T07:32:00Z\n")
        .expect("decodes");
    for name in ["day", "stamp"] {
        assert!(
            value[name].is_string(),
            "{name} decoded to {:?}, want a string so it is a JSON value",
            value[name]
        );
    }
    let encoded = YAML.encode(&value).expect("what was read can be written");
    let again = YAML.encode(&YAML.decode(&encoded).expect("decodes")).expect("encodes");
    assert_eq!(encoded, again, "not a fixed point");
}

// COVERS: FR-4.1 | edge
#[test]
fn a_mapping_key_that_is_not_a_string_is_refused() {
    YAML.decode(b"1: one\n")
        .expect_err("a non-string key has no JSON equivalent");
}

// COVERS: FR-2.3 | negative
#[test]
fn the_wrong_schema_is_not_detected() {
    // FR-2.3: the signature compels a schema and not the right one. An envelope
    // handed the jig schema fails as an ordinary validation error rather than as
    // anything that noticed the mix-up.
    let error = load_formatted_file(
        "output.yaml",
        &wrench::JIG_SCHEMA,
        &YAML,
        &Stub::new(b"success: true\n"),
    )
    .expect_err("the wrong schema still refuses the document");
    assert_eq!(error.step(), "validate");
}

// COVERS: FR-3.4 | edge
#[test]
fn a_schema_checks_shape_and_not_meaning() {
    let schema = anything();
    schema
        .validate(&Value::String("2026-01-01".into()))
        .expect("a string is a string whatever it looks like");
}
