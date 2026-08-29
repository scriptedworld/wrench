//! The schemas that ship with the library, named without a suffix.
//!
//! ```
//! use wrench::schemas;
//!
//! let _ = &schemas::JIG;
//! ```
//!
//! The module carries what kind of thing these are, so the names do not have to.
//! `wrench::JIG_SCHEMA` says schema twice and reads worse the more of them there
//! are.
//!
//! Not to be confused with [`crate::schema`], which is the machinery: the
//! [`Schema`](crate::Schema) trait, `compile_schema`, and the registry a `$ref`
//! resolves against. This module re-exports instances and nothing else.
//!
//! Each is the same static as its older `*_SCHEMA` name, so the two cannot
//! drift the way two copies can. The older ones are kept while consumers move,
//! and this is the spelling to write.

pub use crate::schema::DEFINITIONS_SCHEMA as DEFINITIONS;
pub use crate::schema::ENVELOPE_SCHEMA as ENVELOPE;
pub use crate::schema::JIG_SCHEMA as JIG;
pub use crate::schema::MANIFEST_SCHEMA as MANIFEST;
