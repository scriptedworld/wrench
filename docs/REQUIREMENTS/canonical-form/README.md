# canonical form

**FR-4.1's refusal half is scoped to Go and Python, and the type system is why.**
Every pack covers the row for `property`: all three emit canonical form and are
held to the same fixtures. Its `edge` and `negative` cases test refusing a value
that has no canonical form, and in Rust no such value can be constructed.
`serde_json::Number::from_f64` returns `None` for NaN and
for both infinities, and every one of `Value`'s six variants encodes. Go reaches
the case with a channel under `any`, and Python with `float("nan")`.

So Rust holds the rule at compile time, as it holds FR-3.10, and there is no
runtime consequence left to assert. The scope names those two kinds rather than
the whole row, because scoping the row would stop the checker noticing if Rust
ever dropped its `property` test.

FR-2.2 is the same situation with a different answer. Its negative case is a call
naming no codec or no IO, which in Rust does not compile, and `trybuild` asserts
that it does not. Where a compile failure is what there is to observe, observe
it; scope the row only when there is nothing.
