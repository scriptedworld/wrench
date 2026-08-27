//! What the type system refuses, held to the same standard as what the runtime
//! refuses.
//!
//! Go and Python discharge FR-2.2's negative case by passing nil or None and
//! asserting the call refuses. This pack takes `&dyn Schema`, `&dyn Codec` and
//! `&dyn Reader`, so the equivalent call does not compile and there is nothing
//! to observe at run time. The guarantee is stronger and, without this, it would
//! be recorded nowhere: a signature says what it says until somebody widens it.
//!
//! The expected compiler output is checked in beside each case. Regenerate it
//! after an intentional signature change, and read the diff rather than
//! accepting it:
//!
//!     TRYBUILD=overwrite cargo test --manifest-path rust/Cargo.toml --test compile_fail

// COVERS: FR-2.2 | negative
#[test]
fn a_call_with_no_codec_or_no_io_does_not_compile() {
    trybuild::TestCases::new().compile_fail("tests/compile-fail/*.rs");
}
