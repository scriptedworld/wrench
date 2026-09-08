# wrench, the specification

How wrench is built, for somebody writing a pack or reading one. The contract it
implements is `docs/REQUIREMENTS/`, one file per requirement; the reasoning
behind the shape is `docs/DECISIONS/`; what the project is for is
`docs/PROJECT.md`. This file sits between them and says what the pieces are, how
they fit and what each one promises.

An `FR-` citation names a requirement in that tree. A decision is named by its
slug and a task by its group and ordinal, both findable where they live.

The test it is written to pass: another pack should be implementable from this
file plus the schemas and the fixture set, without reading an existing pack.
Where that is not yet true the gap is named in "What this does not specify".

## The value model

Everything below rests on one decision. **A decoder produces maps, lists and the
JSON scalars, and nothing else** (FR-2.9). The scalars are string, number,
boolean and null. A map key is a string.

A format with a type JSON does not have is reconciled in the decoder. Two rules
settle every case:

- Where the spelling is lossless, coerce. A YAML timestamp decodes to its ISO
  8601 string (FR-2.9), the value being carried whole by the text it was
  written as.
- Where it is not, refuse. A mapping key that is not a string is refused rather
  than stringified, because the coercion is not reversible.

This is what makes one schema validate a file whichever codec read it (FR-3.3),
and what makes a codec substitutable at all. A pack whose YAML decoder hands
back a native date has not implemented the contract, however well it round
trips.

**What happens past the range of a 64-bit integer is decided and not yet
built.** The rule is that such a number widens to a float in every codec and
every pack, visibly, because FR-4.8 gives a whole float a trailing `.0`. The
decision is `parity-is-reached-by-widening-never-by-refusing`.

Today the packs disagree. Python is exact everywhere, its integers being
unbounded; Go is exact in YAML and wrong in JSON; Rust is the reverse. A pack
being written now should implement the widening and expect the existing ones to
follow. Task `parity/40` holds the measurements.

## The two calls

    load_formatted_file(path, schema, codec, reader) -> value
    save_formatted_file(value, path, schema, codec, writer)

Those two are the whole of file handling (FR-2.1). Four arguments, and the
argument order is part of the contract because the fixture set and the parity
check compare packs against each other.

**Load** reads, decodes, then validates:

    reader.read(path)      failure -> read
    codec.decode(bytes)    failure -> parse
    schema.validate(value) failure -> validate
    return value

**Save** validates, encodes, then writes:

    schema.validate(value) failure -> validate
    codec.encode(value)    failure -> encode
    writer.write(path, bytes)  failure -> write

Validation on the way out is not symmetry for its own sake. It stops a caller
writing a structure wrench would refuse to read back (FR-2.4), so a file
produced by a save always survives a load.

The schema argument cannot be omitted (FR-2.2). It can be wrong, and no part of
the library detects that (FR-2.3). That hole is stated in the contract as
permanent, and task `schemas/40` is the design that closes it for
any document carrying its own identifier.

## The four seams

Each argument is an interface with one job, so a format can be added without
inventing a source and a source without inventing a format (FR-2.5).

| Seam | Method | Promises |
|---|---|---|
| `Codec` | `decode(bytes) -> value`, `encode(value) -> bytes` | The format. Knows nothing about where bytes came from. `encode` emits canonical form. |
| `Reader` | `read(path) -> bytes` | The IO on the way in. Handed the path, not the bytes. |
| `Writer` | `write(path, bytes)` | The IO on the way out. Puts the whole contents in place. |
| `Schema` | `validate(value)` | Applies to the decoded structure, not the text. |

**A reader is handed the path rather than bytes** (FR-2.5a). Handing it bytes
would put the open where the caller is, and a test substituting a reader would
then be replacing the parse alone. Handed the path, a substituted reader
exercises every validation path against no filesystem at all.

One reader and one writer ship, both local files, and nothing else (FR-2.8).
Everything wrench serves runs on the machine holding the file, and a test brings
its own.

The shipped writer is atomic (FR-6.3): the bytes go to a temporary file beside
the target and are renamed into place, so a concurrent reader sees the previous
contents or the new ones.

## The wrappers

Two codecs ship, YAML and JSON (FR-2.7), each with a pair of wrappers that
supply the codec and add nothing else (FR-2.10):

    load_yaml_file / save_yaml_file
    load_json_file / save_json_file

Validation stays in the core call, so the seam is unchanged in both directions.

TOML was the third and is retired. No maintained library in any of the four
languages emits its canonical form, and the hand-written emitters that stood in
for one wrote a document they could not read back. FR-2.7 carries the defect and
the three source lines it came from.

**The codec is named, never inferred from the suffix.** Choosing a parser by
filename makes behaviour depend on what a file is called, and renaming a file
would silently change how it is read. That is the implicitness FR-2.2 exists to
remove, so reintroducing it at the wrapper would undo the design one layer up.

## Errors

Every failure a public entry point produces is wrench's own type, carrying the
underlying cause (FR-2.11). Nothing escapes the family, so one catch reaches
every failure wrench can produce, and no consumer ever handles `yaml.YAMLError`
or `serde_json::Error`.

Seven kinds, spelled identically in every pack:

| Kind | Raised when |
|---|---|
| `read` | The reader could not supply the bytes. |
| `parse` | The codec could not turn bytes into a structure. |
| `schema` | The schema itself could not be compiled or resolved. |
| `validate` | The structure did not match the schema. |
| `encode` | The codec could not produce canonical bytes for the structure. |
| `write` | The writer could not put the bytes in place. |
| `usage` | The call was made wrongly, before any file was touched. |

The first six are steps of the two calls and appear in the sequences above.
`usage` is the seventh and sits outside them: a missing schema, codec, reader or
writer. **Rust cannot produce it**, because the same call does not compile
there, and a pack in a language with the same property is right to omit it.

The kinds are the vocabulary a consumer matches on, so a pack exposes them as
data and not only as types. bolt writes one into a reason's `kind`.

Do not make these subclass a language's built-in error hierarchy. It looks right
and is false: a validation failure can be a wrong type, which
`'three' is not of type 'integer'` demonstrates, and in Python `ValueError`
excludes that case by its own definition. FR-2.11 carries the measurement.

A codec is handed bytes and a schema a structure, so neither knows which file it
is working on. Both raise with no path, and the two calls fill it in, so a
consumer unwraps once to reach the cause.

## Canonical form

Canonical form belongs to the save call (FR-4.3), so a caller cannot emit
something valid but written another way. Each codec has one output for one
structure, and that output is no longer promised to be a sibling pack's.

**The packs agree on structure, not on bytes** (FR-5.5). Any pack's output must
decode to the same value in every other pack, and a difference in whitespace is
not a defect. Byte-identity was the older promise and cannot be kept alongside
library emission: no canonical form exists that all four languages' YAML
libraries can produce, libyaml writing block sequences indentless and
hard-coding it while Go's `yaml.v3` indents them and offers only `SetIndent`.
`packs-agree-on-structure-not-on-bytes` carries the measurement and what the
change costs.

Common to both codecs: map keys are sorted, and a float is positional decimal
and never an exponent (FR-4.8). The float rule is the shortest decimal string
that reads back as the same double, with the point where it belongs; a whole
number keeps a trailing `.0`, a negative zero keeps its sign, and NaN and the
infinities are refused.

### The four adapters, which are what a pack implements

A library is taken with adapters and never bare. These four preserve meaning,
which is the half that still has to agree once bytes do not:

    sort the keys                a mapping has no order of its own, so sorting
                                 is what makes two runs over one structure agree
    quote every string and key   `no`, `1.20`, `null` and `10` stay the strings
                                 they were. The key is the sharp one: to a YAML
                                 1.1 reader an unquoted `10:` is an integer key
    positional floats            FR-4.8, and `1e+20` read by `[0-9.]+` yields 1,
                                 which is a defect found in the wild
    null written as the word     an empty value and a missing one should not
                                 look the same to a reader

None of them writes a character of text. A pack that drops one produces a file
that reads back as something else, which is why they are the contract and the
layout is not.

An emitter in the libyaml family takes two settings beside them, both settings
rather than code: the line width off, so a long scalar is never wrapped, and
unicode passed through rather than escaped. libyaml spells them `set_width(-1)`
and `set_unicode(true)`, and Psych takes `line_width` on the dump. Go's
`yaml.v3` offers neither and needs neither: `SetIndent` is the whole of its
emitter API, its own width and unicode functions being unexported, and it wrote
a 9,689-character scalar on one line.

**The quoting adapter is what makes escaping possible at all**, so it is not
independent of the others. A single-quoted YAML scalar has no escapes, so a
control character in one is written raw and read back as something else.
Quote every string and the emitter escapes what it must.

**YAML** (FR-4.1, FR-4.4). Block style, one key to a line. A scalar is quoted
exactly when it is meant to be a string, so `no`, `1.20` and `null` come back as
the strings they were and a boolean stays a boolean. Flow style is valid YAML
and is not what wrench emits, so two versions of a file differ by the lines that
changed.

The complement is the half that surprises people: an unquoted `1.20` was a
number, and that number has no trailing zero, so it round trips as `1.2`. Quote
a version number.

**JSON** (FR-4.6). Two-space indent, one key to a line, keys sorted, trailing
newline. It is `deno fmt` clean, which is deliberate, because the gate already
runs `deno fmt --check` over `schemas/*.json` and a second answer about JSON
layout would put two formatters in one repository. The agreement is one
direction only: `deno fmt` does not sort keys and will collapse a short object
onto one line, so it is a formatter and not a canonical form.

**Control characters** are escaped and never written raw (FR-4.9), using the
escape table of the format being written. That table is a property of the
format, so a pack takes it from its library where the library has it right.
`packs-agree-on-structure-not-on-bytes` measured libyaml's YAML table as
matching wrench's byte for byte, and JSON's escaping comes from the bound
library, that being the part of the library every pack found correct. No value
is refused for carrying a control character.

The packs do not all agree on which non-ASCII characters they escape, and under
structural agreement that is no longer a defect by itself. What is a defect is a
pack that cannot read its own output, and one still cannot: `NEXT_STEPS.md`
carries the measurement.

**A value with no canonical form is refused rather than guessed at** (FR-4.1).
A new codec inherits that rule before it decides anything of its own.

## The schemas

Four ship: `envelope`, `jig`, `manifest` and `definitions`. They are files in
`schemas/`, one copy read by every pack (FR-3.2, FR-3.5), so a consumer names
one instead of carrying a copy free to drift.

Each pack groups them so the names carry no suffix, the grouping saying what
kind of thing they are:

    wrench.schemas.JIG        Python
    wrench.Schemas.Jig        Go, a struct value, having no namespace in a package
    wrench::schemas::JIG      Rust

The older `JIG_SCHEMA` and `JigSchema` spellings are the same objects and are
kept while consumers move. Two names for one object cannot drift the way two
copies can, which is why keeping both costs nothing; only one of them is the
spelling to write.

They stay files in the tree so a YAML language server can be pointed at one
while a jig is being written. A pack compiles them in to link a single static
binary, and what it compiles in is those same bytes.

**A pack discovers them by reading the directory** (FR-3.7), never from a list
of filenames a person maintains. No compiler here can read a directory, so each
pack reads it in a generator instead: Rust in `build.rs` on every build, Go and
Python in `bin/generate-shipped.py` into a committed file. A schema added to
`schemas/` reaches every pack without anybody editing a source file.

The two committed copies are the cost, and they are the drift FR-3.2 exists to
prevent. The gate task `shipped-schemas-are-current` runs the generator with
`--check`, which compares bytes and names the stale file. Rust has no such task,
having no committed copy to go stale.

**A schema is named by the `$id` it declares, never by its filename** (FR-3.6).
A relative filename resolves against whatever directory the process started in,
which puts a local absolute path into a message that travels inside an envelope.

**A `$ref` resolves from the shipped set and the document's own fragments, and
from nowhere else** (FR-3.10). Not the network, not the disk, and with no way to
ask for more. A caller may not redefine a shipped `$id` either, because a
document deciding what the envelope schema means defeats the reason a schema
ships at all.

There are three tiers and they are the whole of it (FR-3.10a):

    within the document    #/$defs/… and #anchor          resolve
    the shipped set        by the $id a schema declares   resolve
    anything else                                         refused

**The tier is decided by the resolved reference, never by its text** (FR-3.10b).
A relative `$ref` resolves against the document's `$id`, so the same string is a
different reference in a different document, and where a document declares no
`$id` the compile name is the base instead. Measured in all three packs.

**A keyword in an instance is data** (FR-3.10c). `$ref`, `$id` and `$schema` are
keywords in a schema and ordinary keys in the document being validated. Nothing
interprets them there, including a `file://` reference whose target exists.

**The refusal reads the same in every pack** (FR-3.10d): `cannot resolve <the
resolved reference>: a schema may reference the shipped schemas and its own
fragments, and nothing else`, as a `schema` error. Three packs refuse by three
mechanisms (a loader, a registry with nothing else in it, and a retriever), and
a consumer cannot tell which language produced the message.

`WRENCH_ALLOW_EXTERNAL_SCHEMA_REFS` was an escape hatch and is retired. It meant
three different things: it let Python fetch over HTTP and read files, let Go read
files only, and did nothing at all in Rust. `SECURITY.md` carries what was
measured and why Rust's `default-features = false` was never the guarantee it
read as.

**A document may declare its format version** as a semver string at the top
level, optional (FR-3.9). Absent claims nothing, which is every document written
before the field existed. Present, a consumer can refuse a major it does not
understand. The definitions format does not carry one, being an open mapping
where reserving a key costs a placeholder name.

Every shipped schema has a fixture that is an instance of it (FR-3.8), and a
fixture declaring a schema is validated against it as well as compared byte for
byte. Byte-identical output between two packs says they agree on the spelling
and says nothing about whether the thing they spelled is a document a consumer
would accept.

A schema checks shape and not meaning (FR-3.4). A value that parsed differently
from how it was written is still a value of the right type, and validation
passes it. Anything relying on a schema to catch a wrong value is relying on the
wrong control.

## What each pack spells

The calls are the same and the spelling is each language's own, by
`each-pack-spells-the-calls-its-own-way`. A pack is idiomatic in its language
before it is symmetrical with its siblings.

| | Go | Python | Rust | Ruby |
|---|---|---|---|---|
| Core calls | `LoadFormattedFile` | `load_formatted_file` | `load_formatted_file` | `load_formatted_file` |
| Error family | `Error` interface with `Step()` | `Error` base class | `Error` enum | `Error < StandardError` |
| Kind vocabulary | `StepRead` and the rest | the exception classes | the enum variants | the exception classes, plus `STEPS` |
| Reading the kind | `Step()` method | `step` property | `step()` method | `step` method, on the instance or the class |
| YAML emission | `yaml.v3` nodes | by hand | by hand | Psych nodes |
| JSON emission | `encoding/json`, floats respelled first | walked by hand for floats | `serde_json` with a float formatter | `JSON.pretty_generate`, floats respelled first |
| Schemas reach the pack by | generated `go/shipped_gen.go` | generated `_shipped.py` | `build.rs` generating `shipped.rs` | nothing yet |
| Validator | santhosh-tekuri/jsonschema | `jsonschema` | `jsonschema` crate | `json_schemer` |

Each pack binds its language's established implementation instead of
implementing JSON Schema itself (FR-5.2). Which one, and why, is
`which-json-schema-library-each-pack-binds`.

The two hand-written YAML emitters are what
`packs-agree-on-structure-not-on-bytes` retired the requirement for, and they
are still in place. A pack written now emits through its library with the four
adapters; the older two are the shape being replaced, not the shape to copy.

**Every pack exposes the same set of schemas** (FR-5.7), and each checks itself
against the directory rather than against another pack. A schema present in one
pack and absent from another is a divergence in the contract, so agreement
follows from each pack answering to the one authority. The Ruby pack does not
carry the shipped set at all yet: it compiles a schema a caller hands it and has
no `Schemas`, so it is the one pack a consumer cannot name `ENVELOPE` through.

## How the packs are held level

Two mechanisms, and neither is shared code (FR-5.5).

The first is JSON Schema's own cross-implementation test suite, which every pack
runs against its own binding.

The second is `testdata/canonical/`, the fixture set, living beside the schemas
so a fixture and every pack it judges move in one commit (FR-5.6). No pack is
ever tested against a different revision of it.

`bin/test-suite-parity.py` checks that every pack's suite covers the same cases.
The authority on an intended divergence is the scope marker on the requirement
row, such as `[python]`, and nowhere else holds a second copy of that list.
Adding a scope marker to silence a parity failure is the one wrong use of it:
the marker is for a row a pack cannot discharge, and a row merely untested in
one pack is the finding.

**The fixture set still compares bytes, and the contract no longer does.** Each
of the twelve cases holds an `input.yaml` and a `canonical.yaml`, and the Go,
Python and Rust suites assert their output equals that golden file. That is a
stricter test than FR-5.5 now asks for, and those three packs pass it; the Ruby
pack does not read the set at all. Re-basing it on structures, so a case is a
value every pack must produce and decode rather than bytes every pack must
reproduce, is open work in `NEXT_STEPS.md`.

The known limits of the mechanism, recorded so they are not rediscovered.
`testdata/canonical/` feeds `input.yaml` only, so JSON decode is exercised
against a single hand-written constant copied into each suite. Every fixture is
pure ASCII, so the set cannot disagree about a character it does not contain.
No fixture holds a string long enough to reach an emitter's line width, so the
set says nothing about folding. A gap in it looks exactly like agreement. Task
`parity/40` holds the measurement and the mechanism that closes it.

## Reaching the library

The Python pack is importable from a source checkout with no install having run
(FR-6.1), and its own suite runs that way on `PYTHONPATH`. Carrying the schemas
as source is what frees it: it resolves them without reference to where it sits,
so a plain install, an editable one and a bare `PYTHONPATH` all work.

Dependencies are on names being importable, not on a resolver having run
(FR-6.2). The pack imports `yaml`, `jsonschema` and `referencing` by name, so a
platform package and a pip install satisfy it identically.

## What this does not specify

Named so a reader stops looking rather than concluding the answer is implied.

**Which schema is the right one for a document.** The signature compels a
schema and cannot check that it is the correct one (FR-2.3).

**What a document's keys mean.** wrench establishes that a file has the form its
schema declares and stops (FR-1.2). What a jig's keys mean and what an
envelope's reasons say belong to the components that produce and consume them.

**Whether an unknown key is an error.** The shipped schemas refuse no unknown
key today, deliberately, and whether that should become a failure or a warning
is open. A jig carrying a key bolt does not read validates here and is refused
one layer later.

**The shape of `metadata.evidence` and `metadata.statistics` in the envelope.**
Both carry a description and no type, so a producer may write either as a
string, a list, a mapping or a number and validation passes.
the inbox entry `the-envelope-schema-does-not-constrain-evidence` holds a
real producer's shape and the range of options.

**Which type a number comes back as within the widened range.** The range rule
is settled and the agreement mechanism is not. Go's YAML gives an `int` where
its JSON gives an `int64`, and `-0` in JSON reads as `-0.0` in Rust and `0` in
the other two. All three are decode defects and none is caught by a fixture set
that feeds YAML only.

**How a pack is published.** Versioning and installation are each language's own
question, and only Python's has been answered. The Ruby pack carries a gemspec
and nothing has been published from it.
