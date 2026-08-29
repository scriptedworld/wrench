//! One error per step, because the steps have different causes and fixes.
//!
//! FR-2.6 says a failing call says which step failed. bolt's FR-6.11 turns that
//! into a hard requirement rather than a nicety: an adapter that exits non-zero,
//! writes no output, or writes something that will not parse has produced no
//! authoritative result, and the reason bolt writes has to say which of the
//! three. Collapsing parse and validate into one type makes that
//! unimplementable, so they are distinct here and will stay distinct.

use std::fmt;

/// The path, spaced, or nothing where a boundary did not have one.
///
/// A codec is handed bytes and a schema a structure, so neither knows which file
/// it is working on. Those fail with an empty path and the two calls fill it in
/// with `at`, rather than wrapping a second time and making a consumer unwrap
/// twice to reach the cause.
fn located(path: &str) -> String {
    if path.is_empty() {
        String::new()
    } else {
        format!(" {path}")
    }
}

/// What a call could not do. Each variant is one step of
/// `reader -> decoder -> value -> validated` or its mirror on the way out.
#[derive(Debug, thiserror::Error)]
pub enum Error {
    /// The reader could not produce bytes.
    #[error("wrench: reading{}: {source}", located(.path))]
    Read {
        path: String,
        #[source]
        source: Box<dyn std::error::Error + Send + Sync>,
    },

    /// The bytes were not the format the codec expected.
    #[error("wrench: parsing{}: {source}", located(.path))]
    Parse {
        path: String,
        #[source]
        source: Box<dyn std::error::Error + Send + Sync>,
    },

    /// The structure did not match the schema. Distinct from Parse: the file
    /// was readable and well formed, and says the wrong thing.
    #[error("wrench: validating{}: {source}", located(.path))]
    Validate {
        path: String,
        #[source]
        source: Box<dyn std::error::Error + Send + Sync>,
    },

    /// The value has no canonical form, so writing it would invent one.
    #[error("wrench: encoding{}: {source}", located(.path))]
    Encode {
        path: String,
        #[source]
        source: Box<dyn std::error::Error + Send + Sync>,
    },

    /// The writer could not put the bytes down.
    #[error("wrench: writing{}: {source}", located(.path))]
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
    /// A parse failure with no path, from a codec that was handed bytes.
    pub(crate) fn parse(source: impl Into<Box<dyn std::error::Error + Send + Sync>>) -> Self {
        Error::Parse {
            path: String::new(),
            source: source.into(),
        }
    }

    /// An encode failure with no path, from a codec that was handed a value.
    pub(crate) fn encode(source: impl Into<Box<dyn std::error::Error + Send + Sync>>) -> Self {
        Error::Encode {
            path: String::new(),
            source: source.into(),
        }
    }

    /// A validation failure with no path, from a schema handed a structure.
    pub(crate) fn validate(source: impl Into<Box<dyn std::error::Error + Send + Sync>>) -> Self {
        Error::Validate {
            path: String::new(),
            source: source.into(),
        }
    }

    /// The same failure said with the path the caller named.
    ///
    /// Used instead of wrapping a second time: a Parse from a codec and a Parse
    /// from load_formatted_file are one event, and nesting them would make a
    /// consumer unwrap twice to reach the cause.
    #[must_use]
    pub fn at(self, path: &str) -> Self {
        match self {
            Error::Read { source, .. } => Error::Read {
                path: path.into(),
                source,
            },
            Error::Parse { source, .. } => Error::Parse {
                path: path.into(),
                source,
            },
            Error::Validate { source, .. } => Error::Validate {
                path: path.into(),
                source,
            },
            Error::Encode { source, .. } => Error::Encode {
                path: path.into(),
                source,
            },
            Error::Write { source, .. } => Error::Write {
                path: path.into(),
                source,
            },
            other => other,
        }
    }
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
