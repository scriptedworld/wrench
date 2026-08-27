//! One error per step, because the steps have different causes and fixes.
//!
//! FR-2.6 says a failing call says which step failed. bolt's FR-6.11 turns that
//! into a hard requirement rather than a nicety: an adapter that exits non-zero,
//! writes no output, or writes something that will not parse has produced no
//! authoritative result, and the reason bolt writes has to say which of the
//! three. Collapsing parse and validate into one type makes that
//! unimplementable, so they are distinct here and will stay distinct.

use std::fmt;

/// What a call could not do. Each variant is one step of
/// `reader -> decoder -> value -> validated` or its mirror on the way out.
#[derive(Debug, thiserror::Error)]
pub enum Error {
    /// The reader could not produce bytes.
    #[error("wrench: reading {path}: {source}")]
    Read {
        path: String,
        #[source]
        source: Box<dyn std::error::Error + Send + Sync>,
    },

    /// The bytes were not the format the codec expected.
    #[error("wrench: parsing {path}: {source}")]
    Parse {
        path: String,
        #[source]
        source: Box<dyn std::error::Error + Send + Sync>,
    },

    /// The structure did not match the schema. Distinct from Parse: the file
    /// was readable and well formed, and says the wrong thing.
    #[error("wrench: validating {path}: {source}")]
    Validate {
        path: String,
        #[source]
        source: Box<dyn std::error::Error + Send + Sync>,
    },

    /// The value has no canonical form, so writing it would invent one.
    #[error("wrench: encoding {path}: {source}")]
    Encode {
        path: String,
        #[source]
        source: Box<dyn std::error::Error + Send + Sync>,
    },

    /// The writer could not put the bytes down.
    #[error("wrench: writing {path}: {source}")]
    Write {
        path: String,
        #[source]
        source: Box<dyn std::error::Error + Send + Sync>,
    },

    /// A schema could not be compiled, or a caller asked for something the
    /// library refuses, such as redefining a shipped schema.
    #[error("wrench: {0}")]
    Schema(String),
}

impl Error {
    /// The step this failure belongs to, as a word a consumer can match on
    /// without matching the variant. bolt writes it into a reason's `kind`.
    pub fn step(&self) -> &'static str {
        match self {
            Error::Read { .. } => "read",
            Error::Parse { .. } => "parse",
            Error::Validate { .. } => "validate",
            Error::Encode { .. } => "encode",
            Error::Write { .. } => "write",
            Error::Schema(_) => "schema",
        }
    }
}

/// A message with no cause of its own, for the places a step fails on a rule
/// rather than on somebody else's error.
#[derive(Debug)]
pub struct Message(pub String);

impl fmt::Display for Message {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for Message {}

pub type Result<T> = std::result::Result<T, Error>;
