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

use std::io;

use serde::Serialize;
use serde_json::ser::{Formatter, PrettyFormatter};
use serde_json::Value;

use crate::codec::Codec;
use crate::float_text::canonical_float_text;

/// The JSON codec.
pub struct JsonCodec;

/// The one instance callers use.
pub const JSON: JsonCodec = JsonCodec;

impl Codec for JsonCodec {
    fn decode(&self, data: &[u8]) -> Result<Value, crate::Error> {
        let mut value: Value = serde_json::from_slice(data).map_err(crate::Error::parse)?;
        widen_past_i64(&mut value);
        Ok(value)
    }

    fn encode(&self, value: &Value) -> Result<Vec<u8>, crate::Error> {
        // `PrettyFormatter` indents with two spaces, which is what the other two
        // packs emit and what `deno fmt` produces. Everything about serde_json's
        // output is right except how it spells a float, so the formatter is
        // wrapped rather than the whole serializer being hand-written: `ryu`
        // switches to an exponent at 1e16, which disagrees with this pack's own
        // YAML codec and with the other two packs. FR-4.8.
        let mut out = Vec::new();
        let formatter = CanonicalFormatter {
            pretty: PrettyFormatter::new(),
        };
        let mut serializer = serde_json::Serializer::with_formatter(&mut out, formatter);
        value
            .serialize(&mut serializer)
            .map_err(crate::Error::encode)?;
        out.push(b'\n');
        Ok(out)
    }
}

/// `PrettyFormatter`, with the number spelling replaced.
///
/// Every method here but the two float ones delegates: `PrettyFormatter` owns
/// the layout and this owns FR-4.8, so the two cannot drift apart.
struct CanonicalFormatter<'a> {
    pretty: PrettyFormatter<'a>,
}

impl Formatter for CanonicalFormatter<'_> {
    fn write_f64<W>(&mut self, writer: &mut W, value: f64) -> io::Result<()>
    where
        W: ?Sized + io::Write,
    {
        writer.write_all(canonical_float_text(value).as_bytes())
    }

    fn write_f32<W>(&mut self, writer: &mut W, value: f32) -> io::Result<()>
    where
        W: ?Sized + io::Write,
    {
        self.write_f64(writer, f64::from(value))
    }

    fn begin_array<W>(&mut self, writer: &mut W) -> io::Result<()>
    where
        W: ?Sized + io::Write,
    {
        self.pretty.begin_array(writer)
    }

    fn end_array<W>(&mut self, writer: &mut W) -> io::Result<()>
    where
        W: ?Sized + io::Write,
    {
        self.pretty.end_array(writer)
    }

    fn begin_array_value<W>(&mut self, writer: &mut W, first: bool) -> io::Result<()>
    where
        W: ?Sized + io::Write,
    {
        self.pretty.begin_array_value(writer, first)
    }

    fn end_array_value<W>(&mut self, writer: &mut W) -> io::Result<()>
    where
        W: ?Sized + io::Write,
    {
        self.pretty.end_array_value(writer)
    }

    fn begin_object<W>(&mut self, writer: &mut W) -> io::Result<()>
    where
        W: ?Sized + io::Write,
    {
        self.pretty.begin_object(writer)
    }

    fn end_object<W>(&mut self, writer: &mut W) -> io::Result<()>
    where
        W: ?Sized + io::Write,
    {
        self.pretty.end_object(writer)
    }

    fn begin_object_key<W>(&mut self, writer: &mut W, first: bool) -> io::Result<()>
    where
        W: ?Sized + io::Write,
    {
        self.pretty.begin_object_key(writer, first)
    }

    fn begin_object_value<W>(&mut self, writer: &mut W) -> io::Result<()>
    where
        W: ?Sized + io::Write,
    {
        self.pretty.begin_object_value(writer)
    }

    fn end_object_value<W>(&mut self, writer: &mut W) -> io::Result<()>
    where
        W: ?Sized + io::Write,
    {
        self.pretty.end_object_value(writer)
    }
}

/// Widens an integer past `i64` to a float, in place. FR-4.10.
///
/// THE ONE BAND THIS PACK KEPT EXACT IN JSON. serde_json reaches for `u64` when
/// a positive integer will not fit `i64`, so values in `(i64::MAX, u64::MAX]`
/// decoded exactly here while anything larger, and anything negative past the
/// boundary, had already become `f64`. The YAML codec never had it, because the
/// YAML parser offers only `i64` or `f64`.
///
/// It is the same shape as the defect the Go pack had in its YAML codec, from
/// the other direction: each pack kept the band its own parser had a type for,
/// so the two disagreed about the value while agreeing about everything else.
fn widen_past_i64(value: &mut Value) {
    match value {
        Value::Number(number) => {
            if let Some(exact) = number.as_u64() {
                if exact > i64::MAX as u64 {
                    *value = Value::from(exact as f64);
                }
            }
        }
        Value::Array(items) => items.iter_mut().for_each(widen_past_i64),
        Value::Object(entries) => entries.values_mut().for_each(widen_past_i64),
        _ => {}
    }
}
