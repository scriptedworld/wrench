# wrench, the specification

How wrench is built, for somebody writing a pack or reading one. The contract it
implements is `docs/REQUIREMENTS/`, one file per requirement; the reasoning
behind the shape is `docs/DECISIONS/`; what the project is for is
`docs/PROJECT.md`. This file sits between them and says what the pieces are, how
they fit and what each one promises.

An `FR-` citation names a requirement in that tree. A decision is named by its
slug and a task by its group and ordinal, both findable where they live.

The test it is written to pass: a fourth pack should be implementable from this
file plus the schemas and the fixture set, without reading an existing pack.
Where that is not yet true the gap is named in "What this does not specify".

## The value model

Everything below rests on one decision. **A decoder produces maps, lists and the
JSON scalars, and nothing else** (FR-2.9). The scalars are string, number,
boolean and null. A map key is a string.

A format with a type JSON does not have is reconciled in the decoder. Two rules
settle every case:

- Where the spelling is lossless, coerce. A YAML timestamp and a TOML date,
  time or datetime all decode to their ISO 8601 string (FR-2.9, FR-4.7).
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
unbounded; Go is exact in YAML and wrong in JSON; Rust is the reverse; TOML
refuses in two packs. A pack being written now should implement the widening and
expect the existing three to follow. Task `parity/40` holds the measurements.

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

Three codecs ship, YAML, JSON and TOML (FR-2.7), each with a pair of wrappers
that supply the codec and add nothing else (FR-2.10):

    load_yaml_file / save_yaml_file
    load_json_file / save_json_file
    load_toml_file / save_toml_file

Validation stays in the core call, so the seam is unchanged in both directions.

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
something valid but written another way. Each codec has one, and every pack
writes the same bytes for the same structure. The fixture set is what holds that
true (FR-5.5, FR-5.6).

Common to all three: map keys are sorted, and a float is positional decimal and
never an exponent (FR-4.8). The float rule is the shortest decimal string that
reads back as the same double, with the point where it belongs; a whole number
keeps a trailing `.0`, a negative zero keeps its sign, and NaN and the
infinities are refused.

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

**TOML** (FR-4.7). A table's scalars first and sorted, then its sections sorted,
with no indentation. Scalars precede sections for correctness and not for
layout, because TOML binds a bare key to the most recent header, so a scalar
written after a section lands inside it.

An array whose every item is a table is repeated `[[path]]` sections, TOML
having no inline form for one. Every other array is inline on one line,
including an empty one. A null is refused, TOML being unable to spell one, and a
top-level value that is not a table is refused for the same reason.

**Control characters** are escaped and never written raw (FR-4.9), using the
escape table of the format being written. YAML's table and TOML's are different
from each other, and each pack writes them by hand so that all three agree byte
for byte. JSON's escaping comes from the bound library, that being the part of
the library the packs found correct. No value is refused for carrying a control
character.

**A value with no canonical form is refused rather than guessed at** (FR-4.1).
That single rule is where the TOML refusals above come from, and it is what a
new codec inherits before it decides anything of its own.

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
from nowhere else** (FR-3.10). Not the network, not the disk. A caller may not
redefine a shipped `$id` either, because a document deciding what the envelope
schema means defeats the reason a schema ships at all.
`WRENCH_ALLOW_EXTERNAL_SCHEMA_REFS=1` restores the bound implementation's own
behaviour and is on borrowed time, the Python binding having already called that
behaviour a vulnerability and begun removing it. The Rust pack cannot offer the
escape hatch, because it declares `jsonschema` with `default-features = false`
and the resolving code is not built.

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

| | Go | Python | Rust |
|---|---|---|---|
| Core calls | `LoadFormattedFile` | `load_formatted_file` | `load_formatted_file` |
| Error family | `Error` interface with `Step()` | `Error` base class | `Error` enum |
| Kind vocabulary | `StepRead` and the rest | the exception classes | the enum variants |
| Reading the kind | `Step()` method | `step` property | `step()` method |
| Schemas reach the pack by | generated `shipped_gen.go` | generated `_shipped.py` | `build.rs` generating `shipped.rs` |
| Validator | santhosh-tekuri/jsonschema | `jsonschema` | `jsonschema` crate |

Each pack binds its language's established implementation instead of
implementing JSON Schema itself (FR-5.2). Which one, and why, is
`which-json-schema-library-each-pack-binds`.

**Every pack exposes the same set of schemas** (FR-5.7), and each checks itself
against the directory rather than against another pack. A schema present in one
pack and absent from another is a divergence in the contract, so agreement
follows from each pack answering to the one authority.

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

The known limit of the fixture mechanism, recorded so it is not rediscovered:
`testdata/canonical/` feeds `input.yaml` only, so JSON and TOML decode is
exercised against a single hand-written constant copied into three suites. A gap
in that set looks exactly like agreement. task `parity/40` holds
the measurement and the mechanism that closes it.

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

**A fourth pack's packaging.** How a pack is published, versioned and installed
is that language's own question, and only Python's has been answered.
