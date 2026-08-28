//! wrench reads, writes and validates the form of the ecosystem's structured
//! files.
//!
//! File handling is two calls. Validation sits in the signature, so nothing
//! reads or writes without naming what the file must conform to. The codec is
//! the format and the reader or writer is the IO, declared separately, which
//! puts the IO boundary wholly outside the call.
//!
//! ```no_run
//! use wrench::{load_formatted_file, ENVELOPE_SCHEMA, YAML, LOCAL_FILE};
//!
//! let envelope = load_formatted_file("output.yaml", &ENVELOPE_SCHEMA, &YAML, &LOCAL_FILE)?;
//! # Ok::<(), wrench::Error>(())
//! ```
//!
//! Rust spells functions in snake case, so these match the contract directly.
//! Go's pack spells them `LoadFormattedFile` because that is how Go spells an
//! exported function; what the packs share is behaviour rather than identifiers.
//!
//! # The value type is the contract
//!
//! Both calls work in `serde_json::Value`. FR-2.9 says what a decoder produces
//! is maps, lists and JSON scalars and nothing else, and that is `Value` in
//! Rust. It is also what `jsonschema` validates, so nothing converts between
//! the validate step and the return.
//!
//! A caller wanting its own struct writes one line rather than walking maps:
//!
//! ```no_run
//! # use wrench::{load_formatted_file, JIG_SCHEMA, YAML, LOCAL_FILE};
//! #[derive(serde::Deserialize)]
//! struct Jig {
//!     tasks: Vec<Task>,
//! }
//!
//! #[derive(serde::Deserialize)]
//! struct Task {
//!     name: String,
//!     // A Rust keyword and a hyphenated key are both ordinary here.
//!     #[serde(rename = "in")]
//!     within: Option<String>,
//!     #[serde(rename = "short-circuit-failure", default)]
//!     stop: bool,
//! }
//!
//! let value = load_formatted_file("bolt.q.yaml", &JIG_SCHEMA, &YAML, &LOCAL_FILE)?;
//! let jig: Jig = serde_json::from_value(value)?;
//! # Ok::<(), Box<dyn std::error::Error>>(())
//! ```
//!
//! There is deliberately no generic `load<T: Deserialize>`. Validation happens
//! on the decoded structure per FR-3.3, and a typed return invites validating
//! after deserialising instead.

pub mod codec;
pub mod json_codec;
pub mod toml_codec;
pub mod errors;
pub mod localfile;
pub mod schema;

pub use codec::{Codec, YamlCodec, YAML};
pub use json_codec::{JsonCodec, JSON};
pub use toml_codec::{TomlCodec, TOML};
pub use errors::{Error, Result};
pub use localfile::{LocalFileIo, Reader, Writer, LOCAL_FILE};
pub use schema::{
    compile_schema, shipped_ids, Schema, DEFINITIONS_SCHEMA, ENVELOPE_SCHEMA, JIG_SCHEMA,
    MANIFEST_SCHEMA,
};

use serde_json::Value;

/// Read `path` through `reader`, decode it with `codec`, and validate the
/// result against `schema`.
///
/// A failure says which step failed, because the steps have different causes
/// and different fixes. See [`Error::step`].
pub fn load_formatted_file(
    path: &str,
    schema: &dyn Schema,
    codec: &dyn Codec,
    reader: &dyn Reader,
) -> Result<Value> {
    let data = reader.read(path).map_err(|source| Error::Read {
        path: path.to_string(),
        source,
    })?;

    let value = codec.decode(&data).map_err(|source| Error::Parse {
        path: path.to_string(),
        source,
    })?;

    schema.validate(&value).map_err(|source| Error::Validate {
        path: path.to_string(),
        source,
    })?;

    Ok(value)
}

/// Validate `value` against `schema`, encode it with `codec` in canonical form,
/// and write it to `path` through `writer`.
///
/// Validation runs before the write, so a caller cannot put down a structure
/// wrench would refuse to read back.
pub fn save_formatted_file(
    value: &Value,
    path: &str,
    schema: &dyn Schema,
    codec: &dyn Codec,
    writer: &dyn Writer,
) -> Result<()> {
    schema.validate(value).map_err(|source| Error::Validate {
        path: path.to_string(),
        source,
    })?;

    let encoded = codec.encode(value).map_err(|source| Error::Encode {
        path: path.to_string(),
        source,
    })?;

    writer.write(path, &encoded).map_err(|source| Error::Write {
        path: path.to_string(),
        source,
    })
}

// ---- per-format wrappers ----------------------------------------------------
//
// These add no behaviour. Each supplies one argument to the two calls above, so
// validation still sits in the signature and the seam is unchanged.
//
// NAMED RATHER THAN INFERRED FROM THE SUFFIX. Choosing a parser by filename
// makes behaviour depend on what a file is called, so renaming one would
// silently change how it is read. FR-2.2 exists to remove that implicitness.

/// Load a YAML file, validated against `schema`.
pub fn load_yaml_file(path: &str, schema: &dyn Schema, reader: &dyn Reader) -> Result<Value> {
    load_formatted_file(path, schema, &YAML, reader)
}

/// Save a structure as canonical YAML, validated against `schema`.
pub fn save_yaml_file(
    value: &Value,
    path: &str,
    schema: &dyn Schema,
    writer: &dyn Writer,
) -> Result<()> {
    save_formatted_file(value, path, schema, &YAML, writer)
}

/// Load a JSON file, validated against `schema`.
pub fn load_json_file(path: &str, schema: &dyn Schema, reader: &dyn Reader) -> Result<Value> {
    load_formatted_file(path, schema, &JSON, reader)
}

/// Save a structure as canonical JSON, validated against `schema`.
pub fn save_json_file(
    value: &Value,
    path: &str,
    schema: &dyn Schema,
    writer: &dyn Writer,
) -> Result<()> {
    save_formatted_file(value, path, schema, &JSON, writer)
}

/// Load a TOML file, validated against `schema`. A native date, time or
/// datetime decodes to its ISO 8601 string, which is what FR-2.9 requires.
pub fn load_toml_file(path: &str, schema: &dyn Schema, reader: &dyn Reader) -> Result<Value> {
    load_formatted_file(path, schema, &TOML, reader)
}

/// Save a structure as canonical TOML, validated against `schema`. Refuses a
/// structure containing null, which TOML cannot spell, and one that is not a
/// table, which TOML has no way to be.
pub fn save_toml_file(
    value: &Value,
    path: &str,
    schema: &dyn Schema,
    writer: &dyn Writer,
) -> Result<()> {
    save_formatted_file(value, path, schema, &TOML, writer)
}
