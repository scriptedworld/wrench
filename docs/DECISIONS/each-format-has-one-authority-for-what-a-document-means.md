# Each format has one authority for what a document means

When the packs disagree about a value, ask what the format says, not which pack
is right. Each format has a different kind of answer.

    YAML   yaml.org's type repository: the resolution regex and the canonical
           form it gives for each type
    TOML   the toml.io v1.0.0 specification, which states the awkward cases
           outright
    JSON   RFC 8259 for the grammar, and for what a number means the IEEE 754
           binary64 its section 6 names as what interoperable readers implement

## Why JSON's authority for numbers is binary64

RFC 8259 is a grammar. It admits `-0` and `1e400` and an integer of any length,
and its grammar alone does not say what any of them mean. Section 6 does say
what a reader can rely on: "Since software that implements IEEE 754 binary64
(double precision) numbers [IEEE754] is generally available and widely used,
good interoperability can be achieved by implementations that expect no more
precision or range than these provide", and integers from -(2^53)+1 to
(2^53)-1 are interoperable, in that implementations agree on them exactly.

So binary64 answers the questions the grammar leaves open. It is the authority
for what a number means and not for how one is written: the spelling of a float
is FR-4.8's, and wrench does not copy any runtime's output.

## What this settled

`-0`. binary64 has a signed zero, so JSON decodes `-0` to a negative zero float.
TOML says `-0` and `+0` are identical to an unprefixed zero and only `-0.0`
carries a sign. YAML's integer regex `[-+]?(0|[1-9][0-9_]*)` admits `-0`, and its
canonical form `0|-?[1-9][0-9]*` has no signed zero. So the same two characters
are a float in one format and an integer in the other two, on three separate
authorities that happen to agree with each other twice.

Where the integer range ends. binary64 is exact only to 2^53. wrench has an
integer type, so it keeps exactness to int64 and widens past it. That is wrench
exceeding its authority's capability without departing from it: the JSON
grammar permits the digits, and binary64 simply cannot hold them.

## The band between 2^53 and int64 is real

It is where a nanosecond timestamp lives. `time.time_ns()` is about
1.79e18, which is 199 times above 2^53 and 5 times below int64 max, and a
64-bit id sits in the same range. A reader holding every number as binary64
returns a nanosecond timestamp silently rounded; through wrench it is exact.

Nothing wrench itself writes goes near it. Its schemas carry one integer field,
`manifest.ordinal`, an execution index. So the range rule protects consumers and
carries none of wrench's own traffic. It is kept because the cost is a few lines
per pack and the failure it prevents is a different number arriving with no
error anywhere.
