//! Schemas, and validating a decoded value against one.
//!
//! The schemas are the files in this repository's `schemas/` directory, read at
//! build time by `build.rs` and embedded. One copy is what stops a Go producer
//! and a Rust producer drifting apart while both believe they conform.
//!
//! THE ID, NOT THE FILENAME, is what a schema is called in an error. A relative
//! filename resolves against whatever directory the process happened to start
//! in, which puts a local absolute path into a message that travels inside an
//! envelope.
//!
//! A SCHEMA MAY REFERENCE THE SHIPPED SET AND NOTHING ELSE, per FR-3.10, and
//! this pack refuses twice over.
//!
//! `jsonschema` is declared with `default-features = false`, so `resolve-file`
//! and `resolve-http` are not built into wrench's own dependency line. **That
//! alone was never the guarantee it read as.** Cargo unifies features across the
//! whole graph, so any other crate in a consumer's build that enables
//! `jsonschema/resolve-http` enables it here, and nothing in this crate would
//! know. The declaration keeps the HTTP client and TLS stack out of a build that
//! does not otherwise ask for them, which is worth having, and it is not a
//! refusal.
//!
//! The refusal is [`LocalOnly`], a retriever that answers every reference the
//! compiler was not already given with wrench's own message. It holds whatever
//! the rest of the graph turned on.

use std::collections::BTreeMap;
use std::sync::OnceLock;

use serde_json::Value;

use crate::errors::{Error, Message};

include!(concat!(env!("OUT_DIR"), "/shipped.rs"));

/// A compiled schema. Validates the maps and lists a codec produced rather than
/// the text, so it is indifferent to how the file was serialised on the way in.
pub trait Schema: Send + Sync {
    /// The identifier this schema is named by in an error.
    fn name(&self) -> &str;

    fn validate(&self, value: &Value) -> Result<(), crate::Error>;
}

/// Every shipped schema, keyed by the `$id` it declares.
///
/// The directory is read by `build.rs` rather than a list kept here, so a schema
/// added to `schemas/` ships without this file being edited. A pack that has to
/// be told about each new schema is one that silently ships one fewer than the
/// others.
fn documents() -> &'static BTreeMap<String, Value> {
    static DOCUMENTS: OnceLock<BTreeMap<String, Value>> = OnceLock::new();
    DOCUMENTS.get_or_init(|| {
        let mut out = BTreeMap::new();
        for (file, text) in SHIPPED {
            let document: Value = serde_json::from_str(text)
                .unwrap_or_else(|e| panic!("wrench: shipped schema {file} is not JSON: {e}"));
            let declared = document
                .get("$id")
                .and_then(Value::as_str)
                .unwrap_or_else(|| panic!("wrench: shipped schema {file} declares no $id"))
                .to_string();
            out.insert(declared, document);
        }
        assert!(!out.is_empty(), "wrench: no shipped schemas");
        out
    })
}

/// The `$id`s the shipped schemas declare.
pub fn shipped_ids() -> Vec<&'static str> {
    documents().keys().map(String::as_str).collect()
}

/// Every shipped schema as a resolution registry, built once.
///
/// A `$ref` between two shipped schemas, or from a caller's schema to a shipped
/// one, resolves from here. Nothing else resolves at all: with `resolve-file`
/// and `resolve-http` not built, there is no retriever to fall back to.
fn registry() -> &'static jsonschema::Registry<'static> {
    static REGISTRY: OnceLock<jsonschema::Registry<'static>> = OnceLock::new();
    REGISTRY.get_or_init(|| {
        jsonschema::Registry::new()
            .extend(documents().iter().map(|(id, document)| {
                (
                    id.as_str(),
                    jsonschema::Resource::from_contents(document.clone()),
                )
            }))
            .expect("wrench: the shipped schemas do not form a registry")
            .prepare()
            .expect("wrench: the shipped registry does not prepare")
    })
}

/// The one sentence every pack gives for a reference it will not follow.
///
/// It names the reference as RESOLVED rather than as written, because a relative
/// `$ref` resolves against the document's `$id` and the two can look nothing
/// alike. Measured 2026-09-03: `/tmp/x.schema.json` under an `$id` of
/// `https://elsewhere.invalid/root.json` resolves to
/// `https://elsewhere.invalid/tmp/x.schema.json`, and quoting what was written
/// would send a reader looking for the wrong thing.
pub(crate) fn unresolved(uri: &str) -> String {
    format!(
        "cannot resolve {uri}: a schema may reference the shipped schemas and its own fragments, \
         and nothing else"
    )
}

/// Refuses every reference the compiler was not already given.
///
/// THIS DOES NOT RELY ON A CARGO FEATURE BEING OFF, and that is the point.
/// `default-features = false` keeps `resolve-http` and `resolve-file` out of
/// wrench's own dependency line, but **Cargo unifies features across the whole
/// graph**: any other crate in a consumer's build that enables
/// `jsonschema/resolve-http` enables it for this build too, and wrench never
/// sees that happen. A retriever that always refuses makes the refusal a
/// property of wrench rather than of what the rest of the graph asked for.
///
/// The crate ships an `OfflineRetriever` that does the same thing, and it is not
/// used here: it is `pub(crate)` to jsonschema, and its message is the crate's
/// rather than wrench's. FR-2.11 says every failure crossing the boundary is
/// wrench's own, and a message is part of a failure.
struct LocalOnly;

impl jsonschema::Retrieve for LocalOnly {
    fn retrieve(
        &self,
        uri: &jsonschema::Uri<String>,
    ) -> Result<Value, Box<dyn std::error::Error + Send + Sync>> {
        Err(unresolved(&uri.to_string()).into())
    }
}

/// Builds a validator with every shipped schema reachable by its own `$id`, so
/// one may reference another and a caller's own schema may reference any of
/// them. Nothing else resolves.
fn build(name: &str, document: &Value) -> Result<jsonschema::Validator, Error> {
    jsonschema::options()
        .with_registry(registry())
        .with_retriever(LocalOnly)
        // THE NAME IS THE BASE WHERE THE DOCUMENT DECLARES NO `$id`, which is
        // what the Go and Python packs already did and this one did not.
        //
        // Measured 2026-09-03 while writing the shared cases: a `$ref` of
        // `/tmp/x.schema.json` in a schema with no `$id` failed here with the
        // crate's own "No base URI is available" before [`LocalOnly`] was ever
        // asked, so the refusal carried neither wrench's sentence nor the
        // resolved reference. The other two resolved it against the name and
        // refused it properly. A document declaring an `$id` is unaffected: the
        // `$id` wins over this in every pack.
        .with_base_uri(name.to_string())
        .build(document)
        .map_err(|e| Error::Schema(format!("compiling schema {name}: {e}")))
}

struct Compiled {
    name: String,
    validator: jsonschema::Validator,
}

impl Schema for Compiled {
    fn name(&self) -> &str {
        &self.name
    }

    fn validate(&self, value: &Value) -> Result<(), crate::Error> {
        if let Err(error) = self.validator.validate(value) {
            let path = error.instance_path().to_string();
            let at = if path.is_empty() {
                String::new()
            } else {
                format!(" at '{path}'")
            };
            return Err(crate::Error::validate(Message(format!(
                "{}{at}: {error}",
                self.name
            ))));
        }
        Ok(())
    }
}

/// Turn a JSON Schema document into a Schema.
///
/// The shipped set are not special: anything in the ecosystem can attach a
/// schema to its own structured files and hand it to the same two calls.
///
/// A caller's schema MAY reference a shipped one by its `$id`. It may reference
/// nothing else, and there is no way to ask for more here: see the module note.
///
/// A caller may not redefine a shipped `$id`, because a document deciding what
/// the envelope schema means is the one thing a shipped schema exists to fix.
pub fn compile_schema(name: &str, document: &str) -> Result<Box<dyn Schema>, Error> {
    if documents().contains_key(name) {
        return Err(Error::Schema(format!(
            "{name} is a shipped schema and cannot be redefined"
        )));
    }
    let parsed: Value = serde_json::from_str(document)
        .map_err(|e| Error::Schema(format!("reading schema {name}: {e}")))?;
    let validator = build(name, &parsed)?;
    Ok(Box::new(Compiled {
        name: name.to_string(),
        validator,
    }))
}

/// One of the schemas that ships with the library, compiled the first time it is
/// used so importing the pack costs nothing.
pub struct Shipped {
    id: &'static str,
    validator: OnceLock<Result<jsonschema::Validator, String>>,
}

impl Shipped {
    const fn new(id: &'static str) -> Self {
        Self {
            id,
            validator: OnceLock::new(),
        }
    }
}

impl Schema for Shipped {
    fn name(&self) -> &str {
        self.id
    }

    fn validate(&self, value: &Value) -> Result<(), crate::Error> {
        let compiled = self.validator.get_or_init(|| {
            let document = documents()
                .get(self.id)
                .ok_or_else(|| format!("no shipped schema declares {}", self.id))?;
            build(self.id, document).map_err(|e| e.to_string())
        });

        match compiled {
            Err(problem) => Err(crate::Error::Schema(problem.clone())),
            Ok(validator) => {
                if let Err(error) = validator.validate(value) {
                    let path = error.instance_path().to_string();
                    let at = if path.is_empty() {
                        String::new()
                    } else {
                        format!(" at '{path}'")
                    };
                    return Err(crate::Error::validate(Message(format!(
                        "{}{at}: {error}",
                        self.id
                    ))));
                }
                Ok(())
            }
        }
    }
}

/// The result envelope every producer in the ecosystem writes.
pub static ENVELOPE_SCHEMA: Shipped =
    Shipped::new("https://scriptedworld.github.io/wrench/envelope.schema.json");

/// The jig a runner reads a project's tasks from.
pub static JIG_SCHEMA: Shipped =
    Shipped::new("https://scriptedworld.github.io/wrench/jig.schema.json");

/// What one task execution was going to be given, written before its command runs.
pub static MANIFEST_SCHEMA: Shipped =
    Shipped::new("https://scriptedworld.github.io/wrench/manifest.schema.json");

/// The values a runner substitutes for a jig's placeholders.
pub static DEFINITIONS_SCHEMA: Shipped =
    Shipped::new("https://scriptedworld.github.io/wrench/definitions.schema.json");
