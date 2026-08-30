# Each format has one authority for what a document means

When the packs disagree about a value, the question is not which pack is right.
It is what the format says, and each format has a different kind of answer.

    YAML   yaml.org's type repository: the resolution regex and the canonical
           form it gives for each type
    TOML   the toml.io v1.0.0 specification, which states the awkward cases
           outright
    JSON   JavaScript on V8, because the grammar in RFC 8259 defines syntax and
           says nothing about what a number means

## Why JSON's authority is a runtime and not a document

JSON's specification is a grammar. It admits `-0` and `1e400` and an integer of
any length, and declines to say what any of them denote, because it describes an
interchange syntax rather than a value model. So a document cannot settle a
question about meaning and something that executes has to.

V8 is that something: it is the reference implementation of the language JSON
was taken from, and `JSON.parse` is the most-run JSON reader in existence.

**It is the authority for meaning and not for output.** `JSON.stringify(-0)` is
`0`, and a value past 2^53 comes back spelled `1e+21`. Both are artefacts of a
runtime with one numeric type, and both would break things wrench guarantees:
the first loses a value it just read, the second is the exponent spelling FR-4.8
exists to forbid. Ask V8 what a document says. Do not copy how it writes one.

## What this settled

**`-0`.** V8 reads it as a signed zero, so JSON decodes it to a negative zero
float. TOML says `-0` and `+0` are identical to an unprefixed zero and only
`-0.0` carries a sign. YAML's integer regex `[-+]?(0|[1-9][0-9_]*)` admits `-0`,
and its canonical form `0|-?[1-9][0-9]*` has no signed zero. So the same two
characters are a float in one format and an integer in the other two, on three
separate authorities that happen to agree with each other twice.

**Where the integer range ends.** V8 loses precision above 2^53 because it has
no integer type. wrench has one, so it keeps exactness to int64 and widens past
it. That is wrench exceeding its authority's capability rather than departing
from it: the JSON grammar permits the digits, and V8 simply cannot hold them.

## The band between 2^53 and int64 is not hypothetical

It is where a nanosecond timestamp lives. `time.time_ns()` is about
1.79e18, which is 199 times above 2^53 and 5 times below int64 max, and a
64-bit id sits in the same range. Through V8 a nanosecond timestamp comes back
silently rounded; through wrench it is exact.

Nothing wrench itself writes goes near it. Its schemas carry one integer field,
`manifest.ordinal`, an execution index. So the range rule is defensive for
consumers rather than load-bearing for wrench's own traffic, and it is kept
because the cost is a few lines per pack and the failure it prevents is a
different number arriving with no error anywhere.
