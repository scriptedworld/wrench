//! The JSON codec: bytes to a structure, and a structure to canonical bytes.
//!
//! Canonical form is two-space indent, one key to a line, and keys sorted.
//! JSON needs no quoting rule because it already has one spelling per type,
//! which is what makes it the cheaper of the formats wrench ships.
//!
//! Keys are sorted for the reason the YAML codec sorts them: a mapping has no
//! order of its own, so sorting is what makes two runs over the same structure
//! produce the same bytes. `serde_json`'s `preserve_order` feature is
//! deliberately NOT enabled, so its map is a `BTreeMap` and iterates sorted.
//!
//! The form is `deno fmt` clean, and that is deliberate.
//! `bolt.wrench-quality.yaml` already runs `deno fmt --check` over
//! `schemas/*.json`, so a second answer about JSON layout would put two
//! formatters in one repository. Measured 2026-08-28 against Go and Python:
//! byte-identical.

use serde_json::Value;

use crate::codec::Codec;

/// The JSON codec.
pub struct JsonCodec;

/// The one instance callers use.
pub const JSON: JsonCodec = JsonCodec;

impl Codec for JsonCodec {
    fn decode(&self, data: &[u8]) -> Result<Value, Box<dyn std::error::Error + Send + Sync>> {
        Ok(serde_json::from_slice(data)?)
    }

    fn encode(&self, value: &Value) -> Result<Vec<u8>, Box<dyn std::error::Error + Send + Sync>> {
        // `to_string_pretty` indents with two spaces, which is what the other
        // two packs emit and what `deno fmt` produces. Used rather than a
        // hand-built serializer so the pack keeps `serde` as a dev-dependency
        // only, which is what lets a caller deserialise without wrench having
        // an opinion about it.
        let mut out = serde_json::to_string_pretty(value)?.into_bytes();
        out.push(b'\n');
        Ok(out)
    }
}
