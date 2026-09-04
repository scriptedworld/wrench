//! How a `$ref` is handled, and what a schema keyword means in each of its roles.
//!
//! The cases here are the cases the Go and Python suites run. The packs were
//! measured against each other on 2026-09-03 before any of these were written,
//! and a divergence here is a divergence in the contract rather than in one
//! binding.

use serde_json::{json, Value};
use std::fs;

/// The sentence FR-3.10d requires of every pack. Held as a constant so a change
/// to the wording fails a test rather than drifting quietly through three
/// repositories' worth of consumers.
const REFUSAL: &str =
    "a schema may reference the shipped schemas and its own fragments, and nothing else";

/// A schema that really is on disk, so "it was not read" is a measurement rather
/// than the absence of a target. It requires a property no instance here
/// carries, so a document validated against it would fail loudly.
const REACHABLE: &str = "/tmp/wrench-reachable.schema.json";

const PERMISSIVE: &str =
    r#"{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object"}"#;

fn seed() {
    fs::write(
        REACHABLE,
        r#"{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object","required":["proof_it_resolved"]}"#,
    )
    .expect("seeding the reachable schema");
}

/// What happened, rather than an assertion, so a table states its own
/// expectation.
fn outcome(name: &str, schema_body: &str, instance: &Value) -> (&'static str, String) {
    match wrench::compile_schema(name, schema_body) {
        Err(e) => ("schema", e.to_string()),
        Ok(schema) => match schema.validate(instance) {
            Err(e) => match e {
                wrench::Error::Schema(_) => ("schema", e.to_string()),
                _ => ("validate", e.to_string()),
            },
            Ok(()) => ("accepted", String::new()),
        },
    }
}

// COVERS: FR-3.10c | negative
#[test]
fn a_keyword_in_an_instance_is_data() {
    // The schema keywords are ordinary keys in a document being validated, and a
    // data file is allowed to carry them. The file this points at EXISTS, so an
    // implementation that resolved it is caught here rather than passing for
    // want of a target.
    seed();
    let file_ref = format!("file://{REACHABLE}");

    let cases: [(&str, Value); 5] = [
        ("a $ref at a file that exists", json!({ "$ref": file_ref })),
        ("a $ref at an http url", json!({"$ref": "http://example.invalid/x.schema.json"})),
        ("an $id", json!({"$id": "https://example.invalid/other"})),
        ("a $schema", json!({"$schema": "https://json-schema.org/draft/2020-12/schema"})),
        (
            "a document that is a schema",
            json!({
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "https://example.invalid/embedded",
                "$ref": file_ref,
            }),
        ),
    ];

    for (what, instance) in cases {
        let (got, detail) = outcome("https://example.invalid/s.schema.json", PERMISSIVE, &instance);
        assert_eq!(got, "accepted", "{what} in an instance was interpreted: {detail}");
    }
}

// COVERS: FR-3.10a | positive
#[test]
fn a_reference_within_the_document_resolves() {
    // Both spellings of an internal reference, each asserted by its VIOLATION:
    // an accepted document says nothing, because a $ref that silently
    // contributed no constraint would accept it too.
    let cases = [
        ("a pointer into $defs", r##"{"$schema":"https://json-schema.org/draft/2020-12/schema","$defs":{"tight":{"type":"string","minLength":3}},"type":"object","properties":{"a":{"$ref":"#/$defs/tight"}}}"##),
        ("an $anchor", r##"{"$schema":"https://json-schema.org/draft/2020-12/schema","$defs":{"t":{"$anchor":"tight","type":"string","minLength":3}},"type":"object","properties":{"a":{"$ref":"#tight"}}}"##),
    ];

    for (what, body) in cases {
        let name = "https://example.invalid/s.schema.json";

        let (got, detail) = outcome(name, body, &json!({"a": "abc"}));
        assert_eq!(got, "accepted", "{what} refused a document it should take: {detail}");

        let (got, _) = outcome(name, body, &json!({"a": "x"}));
        assert_eq!(got, "validate", "{what} did not constrain, so the reference resolved to nothing");
    }
}

// COVERS: FR-3.10b, FR-3.10d | negative
#[test]
fn a_refusal_names_the_resolved_reference() {
    // A relative reference resolves against the document's $id, so the text and
    // the reference are different strings. Naming the text would send a reader
    // looking for something that is not what failed.
    //
    // This also pins that the $id wins over the compile name: the name here is a
    // bare filename, and were IT the base the reference would resolve to a path
    // rather than to elsewhere.invalid.
    let body = r#"{"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"https://elsewhere.invalid/root.schema.json","$ref":"sibling.schema.json"}"#;
    let (got, detail) = outcome("mine.schema.json", body, &json!({"anything": 1}));

    assert_eq!(got, "schema", "a reference outside the shipped set resolved");
    assert!(
        detail.contains("https://elsewhere.invalid/sibling.schema.json"),
        "the refusal does not name the resolved reference: {detail}"
    );
    assert!(detail.contains(REFUSAL), "the refusal is not the shared sentence: {detail}");
}

// COVERS: FR-3.10d | negative
#[test]
fn every_refused_form_gives_the_same_sentence() {
    // One sentence for every shape a reference can take, so a consumer matching
    // on the failure does not need a list of the ways it can be spelled.
    seed();
    let file_ref = format!("file://{REACHABLE}");

    let cases = [
        ("an http url", "http://example.invalid/x.schema.json"),
        ("an https url", "https://example.invalid/x.schema.json"),
        ("a file url", file_ref.as_str()),
        ("an absolute path", REACHABLE),
        ("a relative path", "sibling.schema.json"),
        ("an unshipped wrench", "https://scriptedworld.github.io/wrench/not-shipped.schema.json"),
    ];

    for (what, reference) in cases {
        let body = format!(
            r#"{{"$schema":"https://json-schema.org/draft/2020-12/schema","$ref":"{reference}"}}"#
        );
        let (got, detail) = outcome("https://example.invalid/s.schema.json", &body, &json!({"anything": 1}));

        assert_eq!(got, "schema", "{what} resolved rather than being refused");
        assert!(detail.contains(REFUSAL), "{what} was refused in different words: {detail}");
    }
}

// COVERS: FR-3.10 | negative
#[test]
fn no_environment_variable_opens_a_reference() {
    // WRENCH_ALLOW_EXTERNAL_SCHEMA_REFS was documented before it was retired on
    // 2026-09-03, so somebody may still set it. It meant three different things
    // while it existed: Python fetched over HTTP and read files, Go read files,
    // and this pack did nothing at all — its bound crate never linked the
    // resolving code.
    //
    // THAT LAST PART WAS NOT THE GUARANTEE IT READ AS. Cargo unifies features
    // across the graph, so another crate enabling jsonschema/resolve-http
    // enables it here. The retriever is what this asserts, and it holds whatever
    // the rest of the build turned on.
    seed();
    let body = format!(
        r#"{{"$schema":"https://json-schema.org/draft/2020-12/schema","$ref":"file://{REACHABLE}"}}"#
    );

    for name in [
        "WRENCH_ALLOW_EXTERNAL_SCHEMA_REFS",
        "WRENCH_ALLOW_LOCAL_SCHEMA_REFS",
        "WRENCH_ALLOW_NET_SCHEMA_REFS",
    ] {
        // Removed after each case rather than at the end, so a leftover cannot
        // be what the next one measures.
        unsafe { std::env::set_var(name, "1") };
        let (got, _) = outcome("https://example.invalid/s.schema.json", &body, &json!({"anything": 1}));
        unsafe { std::env::remove_var(name) };

        assert_eq!(got, "schema", "{name}=1 opened a reference");
    }
}
