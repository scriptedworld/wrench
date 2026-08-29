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
    compile_schema, load_formatted_file, save_formatted_file, Codec, Reader, Schema, Writer,
    LOCAL_FILE, YAML,
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
    fn write(
        &self,
        path: &str,
        data: &[u8],
    ) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
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

        let value = YAML
            .decode(&input)
            .unwrap_or_else(|e| panic!("{case}: decoding: {e}"));
        let got = YAML
            .encode(&value)
            .unwrap_or_else(|e| panic!("{case}: encoding: {e}"));

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
    let _ = load_formatted_file(
        "nowhere/output.yaml",
        &wrench::ENVELOPE_SCHEMA,
        &YAML,
        &reader,
    );
    assert_eq!(
        reader.saw_path.borrow().as_deref(),
        Some("nowhere/output.yaml")
    );
}

// COVERS: FR-2.6 | negative
#[test]
fn a_failure_says_which_step_failed() {
    let read = load_formatted_file(
        "gone.yaml",
        &wrench::ENVELOPE_SCHEMA,
        &YAML,
        &Stub::failing(),
    )
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

// COVERS: FR-2.4, FR-4.3 | positive
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
    load_formatted_file(
        "bolt.q.yaml",
        &wrench::JIG_SCHEMA,
        &YAML,
        &Stub::new(nested),
    )
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
    let again = YAML
        .encode(&YAML.decode(&encoded).expect("decodes"))
        .expect("encodes");
    assert_eq!(encoded, again, "not a fixed point");
}

// COVERS: FR-1.2 | negative
#[test]
fn a_mapping_key_that_is_not_a_string_is_refused() {
    // A YAML mapping may be keyed by anything. JSON Schema addresses string
    // keys, so a document wrench cannot describe is refused rather than
    // silently coerced into one it can.
    YAML.decode(b"1: one\n")
        .expect_err("a non-string key has no JSON equivalent");

    let error = load_formatted_file(
        "f.yaml",
        &wrench::ENVELOPE_SCHEMA,
        &YAML,
        &Stub::new(b"1: one\n"),
    )
    .expect_err("a non-string key was accepted through the call");

    // normalise runs inside decode, so a normalisation failure is a parse
    // failure. All three packs say the same word here.
    assert_eq!(error.step(), "parse");
    assert!(
        error.to_string().contains("not a string"),
        "the error does not say what was wrong: {error}"
    );
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

/// A scratch directory under the target tree, cleaned before use.
///
/// `CARGO_TARGET_TMPDIR` rather than the system temporary directory: cargo
/// provides it for integration tests, and it keeps working files inside the
/// tree they belong to.
fn scratch(name: &str) -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join(name);
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(&dir).expect("a scratch directory");
    dir
}

/// Every shipped schema as (filename, contents), read from the one copy the
/// other packs read. The directory is the authority on what ships, never a list
/// in this file.
fn schema_files() -> Vec<(String, String)> {
    let dir = root().join("schemas");
    let mut files: Vec<(String, String)> = fs::read_dir(&dir)
        .expect("schemas/ is readable")
        .filter_map(|entry| entry.ok())
        .map(|entry| entry.path())
        .filter(|path| path.to_string_lossy().ends_with(".schema.json"))
        .map(|path| {
            let name = path
                .file_name()
                .expect("a file")
                .to_string_lossy()
                .to_string();
            let text = fs::read_to_string(&path).expect("a readable schema");
            (name, text)
        })
        .collect();
    files.sort();
    assert!(!files.is_empty(), "schemas/ holds no schemas");
    files
}

/// The `$id` each shipped file declares, paired with the file declaring it.
fn declared_ids() -> Vec<(String, String)> {
    schema_files()
        .into_iter()
        .map(|(name, text)| {
            let document: Value =
                serde_json::from_str(&text).unwrap_or_else(|e| panic!("{name} is not JSON: {e}"));
            let id = document["$id"]
                .as_str()
                .unwrap_or_else(|| panic!("{name} declares no $id, so nothing can reference it"))
                .to_string();
            (id, name)
        })
        .collect()
}

/// A manifest carrying the five locations every execution has, plus whatever
/// the case under test adds.
fn manifest_with(variables: &str) -> String {
    format!(
        "task: build\nordinal: 0\ncommand: cargo build\nvariables:\n\
         \x20 project_root:\n    value: /p\n    from: bolt\n\
         \x20 base_dir:\n    value: /p\n    from: bolt\n\
         \x20 work_dir:\n    value: /p/w\n    from: bolt\n\
         \x20 config_dir:\n    value: /p\n    from: bolt\n\
         \x20 output_dir:\n    value: /p/o\n    from: bolt\n\
         {variables}"
    )
}

// COVERS: FR-1.1, FR-3.2, FR-3.5 | positive
#[test]
fn the_schemas_ship_as_files_beside_the_library() {
    // Present as files is what lets a YAML language server be pointed at one
    // while a jig is being written, and it is what keeps one copy rather than
    // one per pack. This pack embeds them to link a static binary, and what
    // build.rs embeds is these files rather than a copy of its own.
    for name in [
        "envelope.schema.json",
        "jig.schema.json",
        "manifest.schema.json",
        "definitions.schema.json",
    ] {
        let path = root().join("schemas").join(name);
        let text = fs::read_to_string(&path)
            .unwrap_or_else(|e| panic!("{} is not present as a file: {e}", path.display()));
        assert!(
            text.contains("\"$schema\""),
            "{name} does not declare which JSON Schema dialect it is"
        );
    }

    // The pack reads ../schemas and never a copy under rust/. A second copy is
    // the drift FR-3.2 exists to prevent, and it would pass every other test.
    assert!(
        !root().join("rust/schemas").exists(),
        "rust/schemas exists, so this pack carries a copy of its own"
    );
}

// COVERS: FR-3.7, FR-5.7 | regression
#[test]
fn every_shipped_schema_is_exported() {
    // A schema added to schemas/ and picked up by one pack but not another is a
    // divergence in the contract that nothing reports. It has happened: a
    // fourth schema shipped, Go exported it, and Python named three filenames
    // in its own source and did not. Each pack asserts against the directory,
    // so every pack agreeing with the directory is what makes them agree.
    let exported = wrench::shipped_ids();

    for (id, file) in declared_ids() {
        assert!(
            exported.contains(&id.as_str()),
            "{file} declares {id} and this pack exports no schema for it"
        );
    }

    let declared: Vec<String> = declared_ids().into_iter().map(|(id, _)| id).collect();
    for id in &exported {
        assert!(
            declared.iter().any(|d| d == id),
            "this pack exports {id} and no file in schemas/ declares it"
        );
    }
}

// COVERS: FR-5.2 | property
#[test]
fn validation_is_a_real_json_schema_implementation() {
    // $ref resolution, $defs and conditional application are the parts a
    // hand-written checker never gets right. Binding to an established
    // implementation means they work, and this is what that buys.
    let schema = compile_schema(
        "refs.schema.json",
        r##"{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object",
            "properties":{"items":{"type":"array","items":{"$ref":"#/$defs/entry"}}},
            "$defs":{"entry":{"type":"object","required":["id"],
                              "properties":{"id":{"type":"integer"}}}}}"##,
    )
    .expect("a schema using $defs compiles");

    schema
        .validate(&json!({"items": [{"id": 1}]}))
        .expect("a conforming structure was refused");
    schema
        .validate(&json!({"items": [{"id": "one"}]}))
        .expect_err("a $ref'd constraint was not applied, so the reference did not resolve");
}

// COVERS: FR-3.1 | edge
#[test]
fn the_envelope_schema_requires_reasons_only_when_it_failed() {
    // The conditional is the part of the envelope schema most likely to be
    // wrong, because it is the only rule that reads one key to decide another.
    load_formatted_file(
        "f.yaml",
        &wrench::ENVELOPE_SCHEMA,
        &YAML,
        &Stub::new(b"success: true\n"),
    )
    .expect("a passing envelope with no reasons was refused");

    load_formatted_file(
        "f.yaml",
        &wrench::ENVELOPE_SCHEMA,
        &YAML,
        &Stub::new(b"success: false\n"),
    )
    .expect_err("a failing envelope carried no reasons and was accepted");
}

// COVERS: FR-3.1, FR-3.4 | edge
#[test]
fn a_jig_may_declare_it_stands_at_the_repository_root() {
    // The field reaches the working directory and nothing else. It is the
    // jig's, not a jig task's: a tool needing the root needs it wherever it is
    // placed, so a caller cannot grant it per placement.
    let tasks = "tasks:\n  - name: check\n    command: \"true\"\n";

    for declared in [
        "needs-repository-root: true\n",
        "needs-repository-root: false\n",
        "",
    ] {
        let document = format!("{declared}{tasks}");
        load_formatted_file(
            "bolt.q.yaml",
            &wrench::JIG_SCHEMA,
            &YAML,
            &Stub::new(document.as_bytes()),
        )
        .unwrap_or_else(|e| panic!("a jig declaring {declared:?} was refused: {e}"));
    }

    for (what, declared) in [
        ("a string", "needs-repository-root: \"true\"\n"),
        ("a number", "needs-repository-root: 1\n"),
        ("an empty key", "needs-repository-root:\n"),
    ] {
        let document = format!("{declared}{tasks}");
        assert!(
            load_formatted_file(
                "bolt.q.yaml",
                &wrench::JIG_SCHEMA,
                &YAML,
                &Stub::new(document.as_bytes())
            )
            .is_err(),
            "{what} was accepted as needs-repository-root"
        );
    }

    let on_task = b"tasks:\n  - name: child\n    jig: other\n    needs-repository-root: true\n";
    assert!(
        load_formatted_file(
            "bolt.q.yaml",
            &wrench::JIG_SCHEMA,
            &YAML,
            &Stub::new(on_task)
        )
        .is_err(),
        "a jig task carrying needs-repository-root was accepted"
    );
}

// COVERS: FR-3.1, FR-3.4 | edge
#[test]
fn a_manifest_variable_says_which_layer_supplied_it() {
    // Nothing in Go exercised this schema until a change to it broke the Python
    // pack alone. A shipped schema no pack validates against is a shape the
    // gate cannot hold any pack to.
    let accepted = manifest_with(
        "  requirements:\n    value: ../REQUIREMENTS.md\n    from: file\n\
         \x20 all_paths:\n    value:\n      - a.rs\n      - b.rs\n    from: bolt\n",
    );
    load_formatted_file(
        "m.yaml",
        &wrench::MANIFEST_SCHEMA,
        &YAML,
        &Stub::new(accepted.as_bytes()),
    )
    .expect("a manifest naming the layer of each variable was refused");

    for (what, variable) in [
        ("a bare value", "  requirements: ../REQUIREMENTS.md\n"),
        ("a value with no layer", "  requirements:\n    value: x\n"),
        ("a layer with no value", "  requirements:\n    from: jig\n"),
        (
            "a layer outside the three",
            "  requirements:\n    value: x\n    from: environment\n",
        ),
    ] {
        let document = manifest_with(variable);
        assert!(
            load_formatted_file(
                "m.yaml",
                &wrench::MANIFEST_SCHEMA,
                &YAML,
                &Stub::new(document.as_bytes())
            )
            .is_err(),
            "{what} was accepted"
        );
    }
}

// COVERS: FR-3.1 | negative
#[test]
fn a_manifest_keeps_the_five_locations() {
    // Every execution has them whatever else it has, so a manifest missing one
    // is not a smaller manifest, it is a broken one.
    for missing in [
        "project_root",
        "base_dir",
        "work_dir",
        "config_dir",
        "output_dir",
    ] {
        let document = manifest_with("").replacen(
            &format!("  {missing}:\n"),
            &format!("  absent_{missing}:\n"),
            1,
        );
        assert!(
            load_formatted_file(
                "m.yaml",
                &wrench::MANIFEST_SCHEMA,
                &YAML,
                &Stub::new(document.as_bytes())
            )
            .is_err(),
            "a manifest without {missing} was accepted"
        );
    }
}

// COVERS: FR-3.1, FR-3.4 | edge
#[test]
fn a_task_may_allow_an_empty_selection() {
    // An empty selection is a failure by default, because a pattern matching
    // nothing is far more often a stale path than a deliberate one. A task says
    // otherwise for itself, and only where there is a selection to be empty: a
    // command naming neither path variable has none, and a jig task has none
    // either because emptiness is its child's business.
    for (what, document) in [
        ("one execution per path", "tasks:\n  - name: check\n    command: jq . {each_path}\n    matching: [\"*.json\"]\n    optional: true\n"),
        ("one over the whole set", "tasks:\n  - name: check\n    command: jq . {all_paths}\n    matching: [\"*.json\"]\n    optional: true\n"),
        ("declining it explicitly", "tasks:\n  - name: check\n    command: go test ./...\n    optional: false\n"),
        ("omitting it", "tasks:\n  - name: check\n    command: go test ./...\n"),
    ] {
        load_formatted_file(
            "bolt.q.yaml",
            &wrench::JIG_SCHEMA,
            &YAML,
            &Stub::new(document.as_bytes()),
        )
        .unwrap_or_else(|e| panic!("{what} was refused: {e}"));
    }

    for (what, document) in [
        (
            "a command with no selection to be empty",
            "tasks:\n  - name: check\n    command: go test ./...\n    optional: true\n",
        ),
        (
            "a jig task, whose child owns emptiness",
            "tasks:\n  - name: child\n    jig: other\n    optional: true\n",
        ),
    ] {
        assert!(
            load_formatted_file(
                "bolt.q.yaml",
                &wrench::JIG_SCHEMA,
                &YAML,
                &Stub::new(document.as_bytes())
            )
            .is_err(),
            "{what} was accepted"
        );
    }
}

// COVERS: FR-3.1, FR-3.4 | edge
#[test]
fn a_time_limit_is_a_decimal_with_a_unit() {
    // The grammar is deliberately narrower than a float parse, so the runner
    // and this schema stay expressible as the same regex. A jig author gets the
    // error against the document being edited rather than one layer later.
    for limit in ["30s", "1.5m", "2h", "0.5s", ".5s", "90m"] {
        let document = format!(
            "time-limit: {limit}\ntasks:\n  - name: check\n    command: go test ./...\n    time-limit: {limit}\n"
        );
        load_formatted_file(
            "bolt.q.yaml",
            &wrench::JIG_SCHEMA,
            &YAML,
            &Stub::new(document.as_bytes()),
        )
        .unwrap_or_else(|e| panic!("{limit} was refused: {e}"));
    }

    // `30` is the one a jig author actually writes, and it was accepted here
    // and refused by the runner before the schema said anything.
    for (what, document) in [
        (
            "a bare number",
            "tasks:\n  - name: c\n    command: go test ./...\n    time-limit: 30\n",
        ),
        (
            "a list",
            "tasks:\n  - name: c\n    command: go test ./...\n    time-limit: [30]\n",
        ),
        (
            "no unit",
            "tasks:\n  - name: c\n    command: go test ./...\n    time-limit: \"30\"\n",
        ),
        (
            "an unknown unit",
            "tasks:\n  - name: c\n    command: go test ./...\n    time-limit: \"30d\"\n",
        ),
        (
            "exponent notation",
            "tasks:\n  - name: c\n    command: go test ./...\n    time-limit: \"1e3s\"\n",
        ),
        (
            "a sign",
            "tasks:\n  - name: c\n    command: go test ./...\n    time-limit: \"+5s\"\n",
        ),
        (
            "an infinity",
            "tasks:\n  - name: c\n    command: go test ./...\n    time-limit: \"infs\"\n",
        ),
        (
            "on the jig itself",
            "time-limit: 30\ntasks:\n  - name: c\n    command: go test ./...\n",
        ),
    ] {
        assert!(
            load_formatted_file(
                "bolt.q.yaml",
                &wrench::JIG_SCHEMA,
                &YAML,
                &Stub::new(document.as_bytes())
            )
            .is_err(),
            "{what} was accepted"
        );
    }
}

// COVERS: FR-3.1, FR-3.4 | edge
#[test]
fn envelope_evidence_and_statistics_are_objects() {
    // Both carried a description and no type, so a producer could write either
    // as a string, a list or a number and validation passed every time. The
    // member shape stays open: constraining it would bind every producer to one
    // runner's naming.
    let accepted =
        "success: true\nmetadata:\n  evidence:\n    alpha-1:\n      result: /tmp/a\n  statistics:\n    checked: 12\n";
    load_formatted_file(
        "out.yaml",
        &wrench::ENVELOPE_SCHEMA,
        &YAML,
        &Stub::new(accepted.as_bytes()),
    )
    .unwrap_or_else(|e| panic!("a mapping of evidence was refused: {e}"));

    for (what, document) in [
        (
            "evidence as a bare string",
            "success: true\nmetadata:\n  evidence: /tmp/a\n",
        ),
        (
            "evidence as a number",
            "success: true\nmetadata:\n  evidence: 12\n",
        ),
        (
            "statistics as a number",
            "success: true\nmetadata:\n  statistics: 12\n",
        ),
    ] {
        assert!(
            load_formatted_file(
                "out.yaml",
                &wrench::ENVELOPE_SCHEMA,
                &YAML,
                &Stub::new(document.as_bytes())
            )
            .is_err(),
            "{what} was accepted"
        );
    }
}

// COVERS: FR-3.1 | negative
#[test]
fn an_unusable_schema_fails_when_it_is_compiled() {
    // Compiling is where a broken schema should fail, so the failure surfaces
    // where the schema is named rather than later and somewhere else.
    for (what, document) in [
        ("not json", "{ not json at all"),
        ("not a schema", r#"{"type": 42}"#),
    ] {
        assert!(
            compile_schema("broken.schema.json", document).is_err(),
            "{what} compiled, so the failure would have surfaced later and elsewhere"
        );
    }
}

// COVERS: FR-3.2 | regression
#[test]
fn a_validation_error_names_the_schema_by_id_not_by_local_path() {
    // The identifier lands in the error, the error lands in a reason, and a
    // reason travels as evidence. Naming a shipped schema by a relative
    // filename resolved it against whatever directory the process started in,
    // which put an absolute local path in front of every consumer.
    let error = load_formatted_file(
        "f.yaml",
        &wrench::ENVELOPE_SCHEMA,
        &YAML,
        &Stub::new(b"success: \"yes\"\n"),
    )
    .expect_err("an invalid envelope was accepted");

    let message = error.to_string();
    assert!(
        message.contains("scriptedworld.github.io/wrench/envelope.schema.json"),
        "the error does not name the schema by its id: {message}"
    );
    assert!(
        !message.contains("file:///"),
        "the error carries a local filesystem path: {message}"
    );
    if let Ok(home) = std::env::var("HOME") {
        assert!(
            !home.is_empty() && !message.contains(&home),
            "the error carries the running user's home directory: {message}"
        );
    }
}

// COVERS: FR-3.2, FR-3.3 | negative
#[test]
fn a_definitions_file_takes_one_level_of_scalars() {
    let scalars =
        b"requirements: ../REQUIREMENTS.md\nline_length: 100\nstrict: true\nempty: \"\"\n";
    load_formatted_file(
        "d.yaml",
        &wrench::DEFINITIONS_SCHEMA,
        &YAML,
        &Stub::new(scalars),
    )
    .expect("a file of scalars was refused");

    for (what, document) in [
        ("a list value", "tags:\n  - one\n  - two\n"),
        ("a nested value", "python:\n  line_length: 100\n"),
        ("a hyphenated name", "line-length: 100\n"),
        ("a name with a brace", "\"{line_length}\": 100\n"),
        ("a leading underscore", "_leading: 1\n"),
    ] {
        assert!(
            load_formatted_file(
                "d.yaml",
                &wrench::DEFINITIONS_SCHEMA,
                &YAML,
                &Stub::new(document.as_bytes())
            )
            .is_err(),
            "{what} was accepted"
        );
    }
}

// COVERS: FR-3.3 | property
#[test]
fn validation_is_indifferent_to_serialisation() {
    // The same structure written two ways validates the same, because the
    // schema applies to what the parser produced and not to the text.
    let block = "success: false\nreasons:\n  - kind: k\n    message: m\n";
    let flow = "{success: false, reasons: [{kind: k, message: m}]}\n";

    for (style, text) in [("block", block), ("flow", flow)] {
        load_formatted_file(
            "output.yaml",
            &wrench::ENVELOPE_SCHEMA,
            &YAML,
            &Stub::new(text.as_bytes()),
        )
        .unwrap_or_else(|e| panic!("{style} style: {e}"));
    }
}

/// The shipped schemas carrying a top-level version, with a document each that
/// is otherwise valid. `definitions` is absent on purpose: it is an open
/// mapping where every key is a placeholder name, so reserving one costs
/// something the other three do not pay.
fn versioned() -> Vec<(&'static str, &'static dyn Schema, String)> {
    vec![
        (
            "envelope",
            &wrench::ENVELOPE_SCHEMA as &dyn Schema,
            "success: true\n".to_string(),
        ),
        (
            "jig",
            &wrench::JIG_SCHEMA as &dyn Schema,
            "tasks:\n  - name: check\n    command: \"true\"\n".to_string(),
        ),
        (
            "manifest",
            &wrench::MANIFEST_SCHEMA as &dyn Schema,
            manifest_with(""),
        ),
    ]
}

// COVERS: FR-3.9 | edge
#[test]
fn a_format_may_declare_the_version_it_conforms_to() {
    // Optional, because every document written before the field existed carries
    // none and claiming nothing is the honest reading of that. Present, it is
    // semver, so a consumer can refuse a major rather than failing later on a
    // field it cannot find.
    let accepted = [
        "1.0.0",
        "0.1.0",
        "10.20.30",
        "1.0.0-alpha.1",
        "1.0.0+build.5",
        "1.0.0-rc.1+build.5",
    ];
    let refused = [
        "1", "1.0", "v1.0.0", "1.0.0.0", "01.0.0", "", "latest", "1.0.0-",
    ];

    for (name, schema, rest) in versioned() {
        // Absent is valid, which is what makes the field additive.
        load_formatted_file("f.yaml", schema, &YAML, &Stub::new(rest.as_bytes()))
            .unwrap_or_else(|e| panic!("{name}: a document with no version was refused: {e}"));

        for version in accepted {
            let document = format!("version: \"{version}\"\n{rest}");
            load_formatted_file("f.yaml", schema, &YAML, &Stub::new(document.as_bytes()))
                .unwrap_or_else(|e| panic!("{name}: version {version:?} was refused: {e}"));
        }

        for version in refused {
            let document = format!("version: \"{version}\"\n{rest}");
            assert!(
                load_formatted_file("f.yaml", schema, &YAML, &Stub::new(document.as_bytes()))
                    .is_err(),
                "{name}: version {version:?} was accepted and is not semver"
            );
        }

        // A bare number is the mistake this pattern exists to catch: YAML reads
        // 1.0 as a float, and a float is not a version.
        let bare = format!("version: 1.0\n{rest}");
        assert!(
            load_formatted_file("f.yaml", schema, &YAML, &Stub::new(bare.as_bytes())).is_err(),
            "{name}: an unquoted 1.0 was accepted, so it passed as a version"
        );
    }
}

// COVERS: FR-3.9 | property
#[test]
fn the_version_field_is_the_same_in_every_format_that_carries_it() {
    // Written into each schema rather than referenced, because it constrains a
    // scalar rather than describing a shape. Repetition is the cost, so drift
    // is what this checks.
    let mut first: Option<(String, Value)> = None;

    for (name, text) in schema_files() {
        let document: Value = serde_json::from_str(&text).expect("a shipped schema is JSON");
        let Some(version) = document.get("properties").and_then(|p| p.get("version")) else {
            continue;
        };
        match &first {
            None => first = Some((name, version.clone())),
            Some((first_name, first_version)) => assert_eq!(
                version, first_version,
                "the version field in {name} differs from the one in {first_name}"
            ),
        }
    }

    assert!(
        first.is_some(),
        "no shipped schema declares a version field, so this test asserts nothing"
    );
}

// COVERS: FR-1.4 | negative
#[test]
fn an_envelope_missing_success_is_refused() {
    let error = load_formatted_file(
        "output.yaml",
        &wrench::ENVELOPE_SCHEMA,
        &YAML,
        &Stub::new(b"reasons: []\n"),
    )
    .expect_err("an envelope with no success key was accepted");

    assert_eq!(error.step(), "validate");
    assert!(
        error.to_string().contains("success"),
        "the error does not name the missing key: {error}"
    );
}

// COVERS: FR-2.5, FR-2.7 | positive
#[test]
fn codec_and_io_are_independent() {
    // The same codec with two different readers. Neither combination needs a
    // function of its own, which is what declaring them separately buys.
    for (name, bytes) in [
        ("first", &b"success: true\n"[..]),
        (
            "second",
            &b"success: false\nreasons:\n  - kind: k\n    message: m\n"[..],
        ),
    ] {
        load_formatted_file(
            "output.yaml",
            &wrench::ENVELOPE_SCHEMA,
            &YAML,
            &Stub::new(bytes),
        )
        .unwrap_or_else(|e| panic!("{name} reader: {e}"));
    }
}

// COVERS: FR-6.3, FR-2.8 | positive
#[test]
fn local_file_writes_atomically() {
    let dir = scratch("atomic");
    let path = dir.join("output.yaml");
    fs::write(&path, b"previous\n").expect("seeding");

    LOCAL_FILE
        .write(path.to_str().expect("utf-8"), b"next\n")
        .expect("write");

    assert_eq!(
        fs::read_to_string(&path).expect("reading back"),
        "next\n",
        "the target does not hold the new bytes"
    );

    let entries: Vec<_> = fs::read_dir(&dir).expect("listing").collect();
    assert_eq!(
        entries.len(),
        1,
        "the directory holds more than the target, so a temporary was left behind"
    );
}

// COVERS: FR-6.3 | negative
#[test]
fn a_failed_write_leaves_no_temporary_behind() {
    let dir = scratch("failed-write");
    // A path whose parent is a file, not a directory, so the temporary cannot
    // be created and the write fails before it starts.
    let not_a_dir = dir.join("file");
    fs::write(&not_a_dir, b"").expect("seeding");

    let target = not_a_dir.join("output.yaml");
    assert!(
        LOCAL_FILE
            .write(target.to_str().expect("utf-8"), b"x\n")
            .is_err(),
        "writing under a file succeeded, which cannot be right"
    );

    let entries: Vec<_> = fs::read_dir(&dir).expect("listing").collect();
    assert_eq!(
        entries.len(),
        1,
        "the directory holds more than the seeded file"
    );
}

// COVERS: FR-6.3 | edge
#[cfg(unix)]
#[test]
fn a_written_file_is_readable_by_its_consumers() {
    // A temporary is created with the owner's permissions only. Evidence meant
    // to be handed around has to survive being handed around.
    use std::os::unix::fs::PermissionsExt as _;

    let path = scratch("readable").join("output.yaml");
    LOCAL_FILE
        .write(path.to_str().expect("utf-8"), b"success: true\n")
        .expect("write");

    let mode = fs::metadata(&path).expect("stat").permissions().mode() & 0o777;
    assert_eq!(mode, 0o644, "mode is {mode:o}, want 644");
}

// COVERS: FR-2.1, FR-6.3 | positive
#[test]
fn round_trip_through_the_real_filesystem() {
    let path = scratch("round-trip").join("output.yaml");
    let path = path.to_str().expect("utf-8");
    let value = json!({"success": true, "metadata": {"statistics": {"checked": 12}}});

    save_formatted_file(&value, path, &wrench::ENVELOPE_SCHEMA, &YAML, &LOCAL_FILE).expect("save");
    let back =
        load_formatted_file(path, &wrench::ENVELOPE_SCHEMA, &YAML, &LOCAL_FILE).expect("load");

    assert_eq!(back, value, "what was written did not come back");
    assert_eq!(
        back["metadata"]["statistics"]["checked"],
        json!(12),
        "an integer did not survive the round trip as an integer"
    );
}
