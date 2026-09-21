# Which libraries the C++ pack binds

libyaml for YAML, jsoncons for JSON, doctest for the suite. One library per
format, and the pack is not the place to chase a parser's speed.

**Each is taken from upstream at a pinned tag, not from a distribution.** The
build names the version, so what a consumer compiles against is what this file
says rather than what a machine happens to have installed:

    libyaml     0.2.5
    jsoncons    v1.9.0
    doctest     v2.5.3

Debian packages all four, and the probes below were run against both where the
version differed, because a distribution's build is the thing to measure against
rather than the thing to depend on. Pinning costs a fetch at configure time, and
where a build has to run with no network the pinned tree is vendored or cached
rather than the pin being dropped.

`docs/PATTERNS/adopting-a-library-for-a-codec.md` decides adoption: a library is
configured with the four adapters, then asked to read back what it wrote, one
code point at a time. The probes and their output are in clank at
`tasks/wrench/library/cpp/20-adopt-the-libraries`.

## YAML: libyaml, and yaml-cpp is refused

81 code points, the whole of C0 and C1, DEL, NBSP, the line separators, U+FEFF,
the noncharacters, an astral character and a CJK one, each emitted double quoted
with unicode passed through and the width off.

    libyaml 0.2.5     81 of 81 read back as written
    yaml-cpp 0.8.0    73 of 81

yaml-cpp fails the check on the eight noncharacters, and it fails them in its
emitter: U+FDD0, U+FDEF, U+FFFE, U+FFFF, U+1FFFE, U+1FFFF, U+10FFFE and
U+10FFFF are each written as U+FFFD. The value is gone before anything reads it,
which is the loss this pattern exists to catch, and no round trip through
yaml-cpp alone can report it because its own reader is handed the replacement
character and is satisfied.

libyaml's output was then read by the Python pack, which decoded all 81 to the
value that went in. That is the cross-pack half of the check.

Two settings beside the adapters, and both matter. `yaml_emitter_set_unicode(1)`
passes unicode through. `yaml_emitter_set_width(-1)` stops wrapping: a
9,689-character scalar with spaces in it came out as one line at width off and
as 122 lines at width 80.

libyaml refuses a scalar carrying neither a tag nor an implicit flag, with
`neither tag nor implicit flags are specified`. A double-quoted scalar with no
tag sets the quoted flag, not the plain one.

## Resolving a plain scalar is the pack's own code

libyaml hands back the scalar's text and the flags saying how it was written, so
turning `no`, `10` and `2026-01-01` into values is the pack's work and not the
library's. The table to reach, measured by running the Python pack rather than
by reading it:

    no yes on off    strings          null ~ and empty   null
    true             boolean          10 010             integer 10
    0x10             integer 16       1_000              integer 1000
    1.20             float 1.2        1e3                float 1000.0
    2026-01-01       string           12:30              string
    .inf .nan        floats, which canonical form then refuses on the way out

## JSON: jsoncons, and one library is the whole of it

Over the same 81 points, every combination of jsoncons and nlohmann encoding
with jsoncons, nlohmann and simdjson decoding read back what went in, 486 of
486, and the Python pack read all 162 documents the two encoders produced. No
candidate fails the acceptance check, so the choice rests on what else each one
carries.

jsoncons validates, and `jsoncons::json` sorts keys by itself, which is the
first adapter. Binding it for reading and writing as well means the pack holds
one JSON library rather than a parser, a writer and a validator that each have
their own idea of what a value is. nlohmann is bound by nothing: it is neither
lighter than jsoncons nor the fastest reader available.

**Being the fastest reader available is not a property this pack is bought
for.** jsoncons reads about six times slower than simdjson, measured over 61MB
of infobot's transcripts at 259.3ms against 42.5ms, and adding simdjson beside
it would have cost 177,872 bytes of text, 18.6%. Both numbers are real and
neither is the point: wrench establishes that a file has the form its schema
declares, and the files it is handed are jigs, manifests, envelopes and state
files. A second parser in every consumer, with the two kept level by nobody, is
a worse thing to own than a slower one.

**A consumer with a hot path reads it directly, and that is not a failure of the
pack.** infobot scans about 60MB of transcript lines on a first render, on every
Claude Code event, and it keeps simdjson for exactly that: lines nothing
validates, no schema, no canonical form, read and summed. It writes and
validates through wrench, where the form is the contract and nothing is timed.
Its own documentation says why both are linked, because a reader finding two
JSON libraries in one binary deserves the reason at hand.

The line is what a document is for rather than how big it is. A file wrench
loads is validated, because FR-2.2 compels a schema, so the value has to reach
the validator's type. A stream a program reads and sums is not that, and asking
wrench for it buys validation nothing was going to use.

Three decode differences the pack's own code settles, none of them a reason to
refuse the library:

- **Past the signed 64-bit range jsoncons keeps an exact integer**, where
  FR-4.10 says the value widens to a float and the widening is visible. The
  pack widens after decoding, as the Go pack does for the same band.
- **Below int64 min jsoncons returns a big integer** rather than a float, so the
  same widening applies there. simdjson refuses that document outright with
  `BIGINT_ERROR`, which is one more reason the pack is not built on it.
- **jsoncons writes `-0.0` as `0.0`.** The sign survives its decode (`signbit`
  is set), so this is its emitter, and the pack's float adapter spells every
  float itself under FR-4.8, which overrides it.

## Why validation is not a library of its own here

It should be: a validator walks a decoded structure against a schema, and the
parser that produced the structure ought to be nobody's business. That is how
the other packs work. Go's validator takes `any`, Python's takes the objects
`json` and ruamel produce, and neither pack pays for a second representation,
because both languages have one value type everything agrees on.

C++ has none, so every validator brings its own DOM and validates that.
jsoncons validates `jsoncons::json`; blaze validates `sourcemeta::core::JSON`.
Binding either means the value reaching the validate step is that library's
type.

**The adapter-shaped validator exists and is the wrong dialect.** valijson is
header-only, validates through an adapter over whatever JSON library the caller
already has, and ships adapters for twelve of them, Boost.JSON, nlohmann,
RapidJSON and yaml-cpp among them. It implements draft 7. wrench declares 2020-12 (FR-1.4), and
`which-json-schema-library-each-pack-binds` has every other pack on a 2020-12
implementation, so binding a draft 7 validator in one pack would make that pack
accept and refuse different documents from its siblings.

Measured, for whoever revisits this: the four shipped schemas use only `type`,
`properties`, `required`, `minLength`, `pattern`, `items`, `minItems`,
`propertyNames`, `const`, `if`/`then`, `$ref` and `$defs`, all of which draft 7
covers apart from the `$defs` spelling. So the gap is not in what wrench's own
schemas need. It is that a consumer compiles its own schemas through this pack,
and those may use anything 2020-12 has.

What follows for the pack's shape, and task 30 settles it: a document that is
loaded is validated, because FR-2.2 compels a schema, so it has to reach the
validator's type. Bulk reading that is never validated, which is what infobot's
transcript scan is, goes through the codec alone and never builds that type.
The two libraries divide along exactly that line.

## The validator: jsoncons, and blaze is heavier

Two maintained 2020-12 implementations were measured, one packaged and one not.
Measured against wrench's four shipped schemas:

- All four are valid against the 2020-12 meta-schema, and the resolver is never
  asked for the meta-schema, so it is built in. The whole probe was rerun under
  `unshare -rn`, with no network reachable at all, and reported the same.
- A `$ref` outside the shipped set is refused through a resolver the pack
  installs, carrying FR-3.10d's message. A `$ref` to a shipped `$id` resolves
  through the same resolver, and the compiled schema then separates a valid
  envelope from an invalid one.

It is heavy, and the weight cannot be turned down. A 2020-12-only program still
carries symbols for drafts 4, 6, 7 and 2019-09 that nothing in it can reach.

**sourcemeta/blaze v1.0.0 was measured because it implements 2020-12 alone, and
it is the heavier of the two.** The same smallest program, compiling one schema
and validating one document:

    jsoncons v1.9.0    735,281 bytes of symbols   1,063,678 bytes of text
    jsoncons 1.3.2     667,934                      956,255
    blaze v1.0.0     1,649,630                    2,392,701

Blaze answered every question correctly: all four schemas compiled, a valid
envelope separated from an invalid one, a reference outside the resolver
refused, and the whole probe repeated under `unshare -rn`. It is simply larger,
its own JSON core included, so the narrower dialect support does not buy the
smaller binary it looks like it should. jsoncons stays.

The gate's independent validator is `ajv`, which no pack binds, so this changes
nothing about the unanimity check.
