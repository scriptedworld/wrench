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

Six settled rows carry no test. FR-6.1 and FR-6.2 are the Python pack's and
wait for it to exist. FR-5.1, FR-5.1a, FR-5.3 and FR-5.4 state why the project
is shaped as it is rather than a property of a pack, so no test can discharge
them and they are the wrong shape for this document rather than untested. That
is recorded in `NEXT_STEPS.md` and left visible instead of turned green.

---

## 1. What wrench is

| ID | Requirement | |
|---|---|---|
| FR-1.1 | wrench reads, writes and validates the form of the ecosystem's structured files. The schemas and a library for each language live in one repository, so a Go producer and a Python producer work from the same definition rather than from two implementations obliged to keep up with each other. | [A] |
| FR-1.2 | wrench establishes that a file has the form its schema declares and stops there. What a jig's keys mean and what an envelope's reasons say belong to the components that produce and consume them. | [D] |
| FR-1.3 | wrench owns the contract and every component that reads or writes through it is a consumer. No consumer's convenience settles what the contract is, which is why the contract is specified before any pack is written. | [A/D] |
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

## 3. Schemas

| ID | Requirement | |
|---|---|---|
| FR-3.1 | The envelope is one schema handed to those calls and a jig is another. wrench provides structured files with schemas attached, for anything in the ecosystem, rather than an envelope-specific facility. | [A] |
| FR-3.2 | The schemas ship with the library, so a consumer names one rather than carrying a copy that can drift from it. | [A] |
| FR-3.3 | JSON Schema validates the decoded structure, so validation is indifferent to how the file was serialised on the way in. | [A/D] |
| FR-3.4 | A schema checks shape, not meaning. A value that parsed differently from how it was written is still a value of the right type and validation passes it. Anything relying on a schema to catch a wrong value is relying on the wrong control. | [A] |
| FR-3.5 | The schemas are files, reachable in the tree, so a YAML language server can be pointed at one while a jig is being written. A pack may embed them to link a single static binary, and what it embeds is those same files rather than a copy of its own. | [D] |

## 4. Canonical form

| ID | Requirement | |
|---|---|---|
| FR-4.1 | YAML is emitted in canonical form: block style, one key to a line, and a scalar quoted exactly when it is meant to be a string, so its type is never in question. Booleans and numbers stay bare. | [A] |
| FR-4.2 | `no`, `1.20` and `null` therefore survive a round trip as the strings they were, and a boolean stays a boolean. Quoting marks intent, so nothing downstream has to guess which was meant. | [A] |
| FR-4.3 | Canonical form belongs to the save call, so a caller cannot emit something valid but written another way. | [A/D] |
| FR-4.4 | Flow style is valid YAML and so is JSON, and neither is what wrench emits. Two files then differ by the lines that changed rather than by one long line. | [A] |
| FR-4.5 | A structure saved and loaded back yields the structure that went in. | [D] |

## 5. Language packs

| ID | Requirement | |
|---|---|---|
| FR-5.1 | A library per language, each implementing the contract, rather than a C core with bindings. The codecs are the easy half and JSON Schema validation is the hard one, so a C core means implementing the specification rather than binding to one. | [A] |
| FR-5.1a | Cgo also costs static linking and cross-compilation, which is what bolt most wants to keep. | [A] |
| FR-5.2 | Each pack binds to its language's established JSON Schema implementation rather than implementing the specification itself. | [D] |
| FR-5.3 | A pack is written from the contract rather than by reading another pack. Otherwise the first implementation's accidents become the specification, which is the provenance failure this ecosystem exists to avoid. | [A] |
| FR-5.4 | Packs follow demand. Go serves bolt and Python serves toolbox's adapters and checkers; the next waits until something needs it. | [A] |
| FR-5.5 | Packs are held level by JSON Schema's own cross-implementation test suite, plus a shared fixture set covering canonical emission and error shape. Agreement comes from both being tested against the same declared cases, not from shared code. | [A] |
| FR-5.6 | The fixture set holding the packs level lives in this repository beside the schemas, so a fixture and every pack it judges move in one commit and no pack is tested against a different revision of it. | [D] |

## 6. Reaching the library

| ID | Requirement | |
|---|---|---|
| FR-6.1 | The Python pack is importable without an install having run. `dotfiles/bin/setup` runs on `/usr/bin/python3` before mise, uv or pip exist, so a pack needing `pip install` first would mean installing requires the installer. | [A] |
| FR-6.2 | Its YAML support is whatever the platform supplies under that name. Debian's `python3-yaml` satisfies that through the one channel available before any other is, and a pip-installed PyYAML satisfies every consumer that is not the bootstrap case. The dependency is on the name being importable rather than on a resolver having run. | [A] |
| FR-6.3 | A write is atomic: the file is written beside its target and renamed into place, so a reader sees the previous content or the new one and never a partial file. | [A] |

## 7. Open

Each row states a property that must eventually hold and cannot be stated yet.
The questions that would settle them are in `NEXT_STEPS.md`.

| ID | Requirement | |
|---|---|---|
| FR-7.4 | The Python pack reaches its bootstrap consumer by a stated route, whether that is apt's `python3-yaml` as the declared floor or vendoring into dotfiles. | [?] |
