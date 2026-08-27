# wrench, Requirements

Derived from four sources and nothing else: `README.md`, the rows in
`bolt/REQUIREMENTS.md` that state the contract rather than bolt's use of it,
`silo/docs/DECISIONS/yaml-everywhere-validated-against-the-decoded-structure.md`,
and `clank/inbox/wrench/python-library-runs-before-pip-exists/`.

Those rows have left bolt, which now states only its own use of the contract.
The move landed as bolt 3d40517.

Requirements are stated as observable properties. Each says what must be true of
wrench or of a call, not how anything is built.

**Status markers.** `[A]` traces to a direct statement in one of the four
sources. `[D]` is derived from one. `[A/D]` is both. `[?]` is open, recorded so
it is not lost and carrying no test yet.

**Scope markers.** A lowercase marker such as `[python]` names the packs expected
to discharge that row, and **a row carrying none is expected in every pack**.
Only three rows carry one, all in section 6.

That is not documentation. `bin/test-suite-parity.py` reads these markers as the
authority on which divergences are intended, so a row exempt here is exempt in
the check, and nowhere else holds a second copy of that list. Adding a scope
marker to silence a failure is the one wrong use of it: the marker is for a row a
pack **cannot** discharge, where a row merely untested in one pack is the finding.

**Every settled row carries a test.** FACT 2026-08-27:

    python3 ~/.projects/toolbox/bin/test-traceability.py \
        --requirements REQUIREMENTS.md .        # exits 0

**Read the exit status, not the summary.** That checker prints a count and exits
non-zero when a settled row has no test, and this document stood in that state
from before this session until 2026-08-27 while the printed line was being quoted
as a pass. The rows that caused it were design notes and a platform note; each was
retired to `docs/DECISIONS/` or struck once its purpose had gone, never excluded.

---

## 1. What wrench is

| ID | Requirement | |
|---|---|---|
| FR-1.1 | wrench reads, writes and validates the form of the ecosystem's structured files. The schemas and a library for each language live in one repository, so a Go producer and a Python producer work from the same definition rather than from two implementations obliged to keep up with each other. | [A] |
| FR-1.2 | wrench establishes that a file has the form its schema declares and stops there. What a jig's keys mean and what an envelope's reasons say belong to the components that produce and consume them. | [D] |
| FR-1.4 | Every structured file in the ecosystem is YAML, validated as JSON Schema over the decoded structure. wrench does not make that decision and does not get to differ from it. It is where the decision is implemented. | [A] |

## 2. The two calls

| ID | Requirement | |
|---|---|---|
| FR-2.1 | File handling is two calls, `load_formatted_file(path, schema, codec, reader)` and `save_formatted_file(data, path, schema, codec, writer)`. | [A] |
| FR-2.2 | Validation sits in the signature. Nothing reads or writes without naming what the file must conform to, so conformance is a property of the library's surface rather than a discipline every call site has to keep. | [A] |
| FR-2.3 | The signature compels a schema, not the right one. Passing none is impossible; passing the wrong one is not, and no part of the library detects that. | [A/D] |
| FR-2.4 | Validation runs on the way out as well as the way in, so a caller cannot write a structure wrench would refuse to read back. | [A] |
| FR-2.5 | The codec is the format and the reader or writer is the IO, declared separately. A format is then added without inventing a source and a source without inventing a format, rather than needing one function per combination of the two. | [A] |
| FR-2.5a | Separating them puts the IO boundary wholly outside the call. A reader is handed the path, so substituting it in a test exercises the validation paths against no filesystem at all rather than only replacing the parse. | [A/D] |
| FR-2.6 | A failing call says which of the two steps failed: the parser could not load the file, or the structure it produced did not match the schema. The two have different causes and different fixes. | [D] |
| FR-2.7 | YAML is the codec that ships. Every structured file in the ecosystem is YAML, so a second has no consumer today; the codec argument exists so that adding one later is not a change to the two calls. | [D] |
| FR-2.8 | A local file reader and a local file writer ship, and nothing else. Everything wrench serves reads and writes on the machine it is running on, and a test substitutes its own reader rather than needing one shipped to do it. | [D] |
| FR-2.9 | **What a decoder produces is maps, lists and JSON scalars, and nothing else.** A format with a type JSON does not have is reconciled at the decoder rather than left for everything downstream, because that shape is what makes one schema validate a file whichever codec read it, and what makes a codec interchangeable at all. A value with no JSON equivalent is coerced where the spelling is lossless and refused where it is not: a YAML timestamp becomes its ISO 8601 string, a mapping key that is not a string is refused. | [A/D] |

## 3. Schemas

| ID | Requirement | |
|---|---|---|
| FR-3.1 | The envelope is one schema handed to those calls and a jig is another. wrench provides structured files with schemas attached, for anything in the ecosystem, rather than an envelope-specific facility. | [A] |
| FR-3.2 | The schemas ship with the library, so a consumer names one rather than carrying a copy that can drift from it. | [A] |
| FR-3.3 | JSON Schema validates the decoded structure, so validation is indifferent to how the file was serialised on the way in. | [A/D] |
| FR-3.4 | A schema checks shape, not meaning. A value that parsed differently from how it was written is still a value of the right type and validation passes it. Anything relying on a schema to catch a wrong value is relying on the wrong control. | [A] |
| FR-3.5 | The schemas are files, reachable in the tree, so a YAML language server can be pointed at one while a jig is being written. A pack may embed them to link a single static binary, and what it embeds is those same files rather than a copy of its own. | [D] |
| FR-3.6 | A shipped schema may reference another by the `$id` it declares, and the reference resolves from the shipped set alone without reaching the network. A shape two schemas both need is then written once rather than copied into each, because two copies are free to drift and nothing would report it. | [D] |
| FR-3.7 | A pack discovers the shipped schemas by reading the directory they live in, not from a list of filenames in its own source. A schema added to that directory is then available in every pack without a second place having to be remembered. | [D] |
| FR-3.9 | A document may declare the version of its format, as a semver string at the top level, and the field is optional. Absent means the document claims nothing, which is every document written before the field existed, so adding it broke none of them. Present, a consumer can refuse a major it does not understand rather than failing later on a field it cannot find. The definitions format does not carry it, being an open mapping where reserving a key costs a placeholder name. | [A] |
| FR-3.8 | Every shipped schema has a fixture that is an instance of it, and a fixture declaring a schema is validated against it as well as compared byte for byte. Byte-identical output between two packs says they agree on the spelling; it does not say the thing they spelled is a document a consumer would accept. A schema nothing is ever validated against is one nobody knows compiles. | [D] |

## 4. Canonical form

| ID | Requirement | |
|---|---|---|
| FR-4.1 | YAML is emitted in canonical form: block style, one key to a line, and a scalar quoted exactly when it is meant to be a string, so its type is never in question. Booleans and numbers stay bare. | [A] |
| FR-4.2 | `no`, `1.20` and `null` therefore survive a round trip as the strings they were, and a boolean stays a boolean. Quoting marks intent, so nothing downstream has to guess which was meant. | [A] |
| FR-4.3 | Canonical form belongs to the save call, so a caller cannot emit something valid but written another way. | [A/D] |
| FR-4.4 | Flow style is valid YAML and so is JSON, and neither is what wrench emits. Two files then differ by the lines that changed rather than by one long line. | [A] |
| FR-4.5 | A structure saved and loaded back yields the structure that went in. | [D] |

## 5. Language packs

Why there is a library per language, why a pack is written from the contract, and
what decides when the next pack is built are recorded in `docs/DECISIONS/`. They
state why the project is shaped as it is rather than a property anything can
test, and four rows saying so were retired from this table on 2026-08-26.

| ID | Requirement | |
|---|---|---|
| FR-5.2 | Each pack binds to its language's established JSON Schema implementation rather than implementing the specification itself. | [D] |
| FR-5.5 | Packs are held level by JSON Schema's own cross-implementation test suite, plus a shared fixture set covering canonical emission and error shape. Agreement comes from both being tested against the same declared cases, not from shared code. | [A] |
| FR-5.6 | The fixture set holding the packs level lives in this repository beside the schemas, so a fixture and every pack it judges move in one commit and no pack is tested against a different revision of it. | [D] |
| FR-5.7 | Every pack exposes the same set of schemas, and each pack's set matches the directory rather than the other pack's. A schema present in one pack and absent from another is a divergence in the contract, so each pack checks itself against the one authority and agreement between them follows. | [D] |

## 6. Reaching the library

**FR-6.1 and FR-6.2 are the Python pack's alone**, and are the only rows
here that one pack holds and another cannot. They are about a Python pack reaching
a Python environment; the Go pack cannot discharge them and should not try. Every
other row states one contract that every pack implements, and both suites cite it.

**So a `COVERS:` mark for these three appearing only in `python/tests/` is a
statement rather than a gap.** Anywhere else in this document, a row cited by one
suite and not the other is the divergence FR-5.7 exists to catch.

| ID | Requirement | |
|---|---|---|
| FR-6.1 | The Python pack is importable from a source checkout, with no install having run. Its own suite runs that way, on `PYTHONPATH`, and the pack reads `schemas/` from the repository rather than from package data, which is why an editable install is the only supported form. ~~`dotfiles/bin/setup` runs on `/usr/bin/python3` before mise exists~~ **restated 2026-08-26**: that was the original motivation and it was disproven. Nothing in the bootstrap window imports wrench, and nothing is planned to. See `docs/DECISIONS/the-pack-is-installed-after-mise-not-before.md`. | [A/D python] |
| FR-6.2 | The pack's dependencies are on names being importable in the environment it is installed into, not on a resolver having run there. It imports `yaml`, `jsonschema` and `referencing` by name, so a platform package and a pip install satisfy it identically. ~~Debian's `python3-yaml` through the one channel available before any other is~~ **restated 2026-08-26**: that framing rested on the bootstrap window, which does not consume this pack. | [A/D python] |
| FR-6.3 | A write is atomic: the file is written beside its target and renamed into place, so a reader sees the previous content or the new one and never a partial file. | [A] |

## 7. Open

Each row states a property that must eventually hold and cannot be stated yet.
The questions that would settle them are in `NEXT_STEPS.md`.

| ID | Requirement | |
|---|---|---|
This section is empty. FR-7.4 was the last open row and it was answered on
2026-08-26; see `## Retired`. An empty section is left standing rather than
deleted, because the numbering continues from it and a reader meeting `FR-7.x`
elsewhere should find where the series went.

## Retired

A requirement can be retired or superseded. **Its ID is never reused**, because
reuse silently rewrites what every existing reference to that ID meant and
nothing about the new row looks wrong. A reader meeting one of these in an old
commit or another project's document finds where it went here.

Numbering therefore has gaps, and a gap is the record working rather than an
oversight.

The FR-7 rows were open questions that building the Go pack answered, which is
the argument for building early: a decision you have to make to write the code is
one you have made by writing it.

The FR-5 rows were design notes sitting in a requirements table. Each said why
the project is shaped as it is rather than stating a property of wrench, so no
test could ever discharge one and the gate reported four permanently uncovered
rows. They moved to `docs/DECISIONS/` intact when the docs tree was created, and
nothing was lost. No test cited any of them, so no `COVERS:` mark needed
cleaning up.

| ID | Retired | Superseded by |
|---|---|---|
| FR-1.3 | 2026-08-26 | `docs/DECISIONS/wrench-owns-the-contract-and-consumers-do-not.md`. It stated who decides rather than a property of wrench. The Go test citing it was testing FR-2.3 and now cites that alone. |
| FR-6.2a | 2026-08-27 | Nothing. Its purpose went with FR-7.4. It recorded that `/usr/bin/python3` supplies no `jsonschema`, which mattered only while the bootstrap window was believed to be a consumer of this pack. It is not, so the row stated a fact about an interpreter nothing here uses, and no test could ever have discharged it. `docs/DECISIONS/the-pack-is-installed-after-mise-not-before.md` keeps the measurement. |
| FR-7.4 | 2026-08-26 | Answered, not superseded. There is no bootstrap consumer to reach: nothing in `dotfiles/bin/` imports wrench or reads YAML, and the pack is installed after mise exists. `docs/DECISIONS/the-pack-is-installed-after-mise-not-before.md` |
| FR-5.1 | 2026-08-26 | `docs/DECISIONS/a-library-per-language-not-a-c-core.md` |
| FR-5.1a | 2026-08-26 | `docs/DECISIONS/a-library-per-language-not-a-c-core.md` |
| FR-5.3 | 2026-08-26 | `docs/DECISIONS/a-pack-is-written-from-the-contract.md` |
| FR-5.4 | 2026-08-26 | `docs/DECISIONS/packs-follow-demand.md` |
| FR-7.1 | 2026-08-26 | FR-2.7. YAML is the codec that ships. |
| FR-7.2 | 2026-08-26 | FR-2.8. A local file reader and writer ship, and nothing else. |
| FR-7.3 | 2026-08-26 | FR-3.5. The schemas are files, and a pack may embed those same files. |
| FR-7.5 | 2026-08-26 | FR-5.6. The fixture set lives here beside the schemas. |
