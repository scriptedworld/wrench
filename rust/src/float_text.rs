//! The one spelling of a float, shared by all three of this pack's codecs.
//!
//! FR-4.8. Positional decimal, never an exponent. The digits are the shortest
//! decimal string that reads back as the same `f64`, placed with the decimal
//! point where it belongs rather than moved into an `e`. A whole number keeps a
//! `.0`, so a float never reads back as an integer.
//!
//! The rule carries no threshold on purpose. Every alternative needs a magnitude
//! at which the spelling changes, and that number then has to be stated in the
//! contract and implemented identically in nine places. "Never" is the only
//! answer with nothing to get wrong, and the only one a consumer parsing with a
//! naive numeric pattern reads correctly: `1e+06` matched by `[0-9.]+` yields 1,
//! which is how this defect was found.
//!
//! The cost is bounded: 326 characters for a subnormal near the bottom of the
//! range, 311 for the largest finite double.
//!
//! **This pack was already right and is the reason the rule is spelled this
//! way.** `Display` for `f64` is positional and shortest-round-trip, so the two
//! hand-written codecs here needed no change; what moved is that all three now
//! ask one function rather than three places agreeing by coincidence.
//!
//! NaN and the infinities cannot reach here: `serde_json::Number` refuses to
//! hold them, so the value type rejects them before a codec is asked.

/// The canonical spelling of one float.
pub(crate) fn canonical_float_text(value: f64) -> String {
    let text = format!("{value}");
    if text.contains('.') {
        text
    } else {
        format!("{text}.0")
    }
}
