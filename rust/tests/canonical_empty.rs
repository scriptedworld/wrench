//! An empty container has one spelling, and it is the short one.
//!
//! The recursive path never reaches this arm, so line coverage read it as
//! covered while the branch went untaken — found in the Python pack on
//! 2026-09-04 when the gate began judging branches. Asserted here because a
//! pack agreeing about full containers and differing about empty ones is
//! exactly what a shared case set exists to catch.

use serde_json::json;
use wrench::{Codec, JSON};

// COVERS: FR-4.6 | edge
#[test]
fn json_empty_containers_are_short() {
    let cases: [(&str, serde_json::Value, &str); 3] = [
        ("an empty document", json!({}), "{}\n"),
        ("an empty mapping", json!({"v": {}}), "{\n  \"v\": {}\n}\n"),
        ("an empty sequence", json!({"v": []}), "{\n  \"v\": []\n}\n"),
    ];
    for (name, value, want) in cases {
        let encoded = JSON.encode(&value).expect("encode");
        assert_eq!(String::from_utf8_lossy(&encoded), want, "{name}");
    }
}

// COVERS: FR-4.6 | edge
#[test]
fn json_nested_empty_containers_keep_the_short_spelling() {
    let encoded = JSON
        .encode(&json!({"a": {"b": {}}, "c": [[]]}))
        .expect("encode");
    let want = "{\n  \"a\": {\n    \"b\": {}\n  },\n  \"c\": [\n    []\n  ]\n}\n";
    assert_eq!(String::from_utf8_lossy(&encoded), want);
}
