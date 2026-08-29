# FR-2.11

| ID | Requirement | |
|---|---|---|
| FR-2.11 | Every failure a public entry point produces is wrench's own error type, never a bound library's, and it carries the underlying cause. The six kinds are distinct and named identically in every pack: `read`, `parse`, `schema`, `validate`, `encode`, `write`. A consumer can match one kind, or the family, without naming a dependency. | |

**Six kinds on three axes**, and the pairs are what make them worth separating:

    read / write        IO, and nothing to do with the content
    parse / encode      the bytes and the value would not convert
    schema / validate   the schema is wrong, or the value is

**`schema` against `validate` is the distinction most easily lost.** A schema
that will not compile, or whose `$ref` will not resolve, is a fault in the schema:
nothing can be checked against it, and the fix is to the schema. A document
failing a schema that is fine is a fault in the document. Both were `ValueError`
in Python and both were the validator's own type in Go until FR-2.11, so a
consumer could not tell "your schema is broken" from "your file is wrong".

**The step word is not the message's gerund.** The message reads
`wrench: parsing f.yaml: ...` and the step is `parse`. One is prose for a person,
the other a token a consumer compares against, and bolt writes the token into a
reason's `kind`.

**The cause is always reachable** — Python `__cause__`, Go `errors.Unwrap`, Rust
`source()`. A wrap that discarded it would be worse than the leak it replaced,
because the leak at least says what went wrong.

**Every pack exposes the family**, so "was this wrench's fault" is one check
rather than six: Python's `WrenchError` base, Rust's `Error` enum, Go's `Error`
interface. Go had neither a base type nor a step until FR-2.11 and needed both,
which is what makes this a contract row rather than three implementations that
happen to agree.

**No kind inherits from a language's built-in error, and this is the part that
looks wrong until it is measured.** Python's `ValueError` is "inappropriate
argument value (of correct type)", `validate` means the value does not match its
schema, and Python's own `json.JSONDecodeError` is a `ValueError`. The inference
is obvious and it is false. Measured against
`{"count": {"type": "integer", "minimum": 0}}`:

    {"count": -1}        -1 is less than the minimum of 0    a VALUE problem
    {"count": "three"}   'three' is not of type 'integer'    a TYPE problem

The second is `TypeError` by Python's own definition, and `ValueError` excludes
it in as many words. **A single wrench kind spans both**, so declaring
`ValidationError` a `ValueError` asserts something untrue of a whole class of
schema keyword. `EncodeError` is the same shape: a NaN has no canonical form
because of its value and an `object()` because of its type.

So wrench's six kinds are **orthogonal** to the value-against-type split a
language draws, and a consumer catches the family or the kind. This also explains
why `except ValueError` stopped working when the wraps landed rather than merely
recording that it did: it was never a statement about wrench's contract, only
about what one bound library happened to raise.

`docs/DECISIONS/every-error-crossing-the-boundary-is-a-wrench-error.md` carries
why, and what each pack's migration cost.
