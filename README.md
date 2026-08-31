# wrench

One definition of what a structured file may contain, and a library in each
language that holds to it.

When several programs read and write the same file, each one grows its own
reader, its own emitter, and its own idea of what a valid document is. They
drift, and every one of them believes it conforms. wrench exists so there is one
place that owns the answer.

A pack is the library for one language. Three ship, in Go, Python and Rust, and
they are not ports of each other: each binds its own JSON Schema validator and
its own parsers, and each is written from the same written contract. What makes
them one library instead of three is a property that is tested, not intended.

## The guarantee

The same document, through any pack and any codec, produces the same bytes.

Standard libraries disagree about how to spell ordinary values, quietly, in
ways that survive every test until a consumer notices:

| value | Go | Python | Rust |
|---|---|---|---|
| `1000000.0` | `1e+06` | `1000000.0` | `1000000.0` |
| `1e21` | `1e+21` | `1e+21` | `1000000000000000000000.0` |

Those were wrench's own three packs, and no error was raised anywhere.

Every pack now writes a float in positional decimal, never an exponent, with the
shortest digits that read back identically, and escapes a control character in
the format's own spelling rather than emitting it raw.

What holds it true is a shared fixture set in `testdata/canonical/`, read by all
three suites, and a parity check that fails when a case is covered in one suite
and missing from another. No pack is the oracle for another: if two disagree,
the fixture is right.

## How it is held to that

    cd go     && go test ./...
    cd python && python3 -m pytest
    cd rust   && cargo test

    ./bin/test-suite-parity.py --requirements docs/REQUIREMENTS \
        --suite go='go/*_test.go' \
        --suite python='python/tests/*.py' \
        --suite rust='rust/tests/*.rs' .

Three suites and a checker that compares them **against each other**. The parity
check fails when a case is covered in one pack and missing from another, which
is the only thing standing between "three libraries" and "one library with three
bindings". It stands at the root because no pack can run it: a pack that could
would have to know about its siblings.

**The contract is written down and traced to the tests.** `docs/REQUIREMENTS/`
holds one file per requirement, and every test names the requirement it
discharges in a comment above it:

    // COVERS: FR-4.4 | negative

A checker walks both directions. A test citing a requirement that does not exist
fails; a requirement no test cites fails too, unless its row is marked as an open
decision. So a requirement cannot quietly lose its test, and a test cannot
quietly stop discharging anything.

**A check that matches nothing is a check that passes.** The parity globs above
are load-bearing, so they are tested by being pointed at the wrong place:

    $ ./bin/test-suite-parity.py --suite go='*_test.go' ...
    parity: suite 'go' matched no files at '*_test.go'
    exit 2

That refusal is the point. Run with the correct glob it reports 66 tests held
level across the three suites, and a scan that found nothing must never be
reported as a scan that found nothing wrong.

## The two calls

    load_formatted_file(path, schema, codec, reader)
    save_formatted_file(data, path, schema, codec, writer)

Validation is in the signature, so nothing reads or writes without naming what
the file must conform to. There is no unvalidated path to fall into.

The codec and the IO are separate arguments, which puts the filesystem outside
the call: a test substitutes a reader and exercises every validation path
against no disk at all.

Three codecs ship, each with a pair of wrappers that supplies it and adds
nothing else:

    load_yaml_file  save_yaml_file
    load_json_file  save_json_file
    load_toml_file  save_toml_file

The codec is named and never guessed from the file extension, because choosing a
parser by filename makes behaviour depend on what a file is called.

A schema is an ordinary JSON Schema file, validated against the decoded
structure, so a YAML document is held to a JSON Schema without either format
needing to know about the other. Four ship, and a caller may pass its own.

## The packs

Go, under `go/`.

    import "github.com/scriptedworld/wrench/go"

    envelope, err := wrench.LoadFormattedFile(
        path, wrench.Schemas.Envelope, wrench.YAML, wrench.LocalFile)

That import path is the module path `go/go.mod` declares, and the Go toolchain
resolves a module path as a URL. `go get` will work once the repository is
published at exactly that path, and not before. Until then a consumer reaches
the pack from a checkout, through a `replace` directive or a `go.work` file.

Python, under `python/`.

    from wrench import load_formatted_file, schemas, YAML, LOCAL_FILE

    envelope = load_formatted_file(path, schemas.ENVELOPE, YAML, LOCAL_FILE)

Rust, under `rust/`.

    use wrench::{load_formatted_file, schemas, YAML, LOCAL_FILE};

    let envelope = load_formatted_file(path, &schemas::ENVELOPE, &YAML, &LOCAL_FILE)?;

What comes back is that language's natural shape for JSON (`map[string]any`,
`dict`, `serde_json::Value`), so nothing converts between validating and
returning.

`uv pip install python/` installs the Python pack, and any install form works
including a bare `PYTHONPATH`, because the pack carries the schemas as generated
source and resolves them without reference to where it sits. The Rust crate is
taken by path: `build.rs` reads `schemas/` from above the crate directory, which
is outside anything `cargo package` would carry.

A language gets a pack when something needs to read or write a structured file
in it. Why this is a library per language instead of a C core with bindings is
`docs/DECISIONS/a-library-per-language-not-a-c-core.md`.

## Errors

Every failure that crosses the boundary is wrench's own type, whatever the
library underneath raised, and it names which step failed: `read`, `parse`,
`validate`, `encode`, `write`, `schema` or `usage`. A consumer matches on the
word without naming a type, and `docs/SPEC.md` says what raises each one.

Nothing escapes the family, so one catch reaches every failure wrench can
produce: `wrench.Error` in Python and Rust, and the `Error` interface in Go. The
cause is always preserved, so a caller who wants the underlying error can reach
it.

One trap, for Python callers. These derive from `Exception` and deliberately not
from `ValueError`, because a validation failure can be a wrong type, which
`'three' is not of type 'integer'` is, and `ValueError` excludes that case by its
own definition. So

    except ValueError:          # catches nothing from wrench

silently stops catching, and an uncaught validator looks exactly like a passing
one from anywhere except a test on the refusal path. Catch `wrench.Error`, or a
specific one such as `wrench.ValidationError`.

## What it will not do

Every save writes canonical form. Keys are sorted, layout is fixed, and comments
do not survive a load. That is what the guarantee costs, and it makes wrench the
wrong writer for a file a person edits: a config with comments and a deliberate
entry order goes in and comes out reordered and stripped. Use a
round-trip-preserving editor there, such as `tomlkit` in Python, and wrench for
the read half, where a config file is usually unchecked anyway.

Machine-written files are what canonical form is for: envelopes, manifests,
queue entries. Nobody has typed a note into one and the ordering carries no
meaning.

A schema establishes that a document has the form it declares, and stops. What
the keys mean belongs to whatever produces and consumes them. The signature
compels a schema and cannot check that it is the right one, which `docs/SPEC.md`
states as a permanent hole rather than a defect awaiting a fix.

## What is not ready

Nothing here is published to a package index, so every pack is taken from a
checkout today. The Rust crate cannot be packaged for one at all until
`build.rs` stops reading the schemas from above the crate directory.

The packs disagree about which type a number comes back as inside the widened
range, and about `-0`. The range rule is settled and the agreement mechanism is
not. TypeScript and Ruby packs are named and not built.

`NEXT_STEPS.md` has the rest, with the measurements behind each.

## Reading further

    docs/SPEC.md          how the pieces fit, written so that a fourth pack
                          could be built from it
    docs/REQUIREMENTS/    the contract, one file per requirement
    docs/DECISIONS/       why the project is shaped as it is
    CONTRIBUTING.md       how to build it, test it, and get a change accepted
    SECURITY.md           the trust boundary, and how to report a vulnerability

## Licence

Apache-2.0. `LICENSE` carries the terms and `NOTICE` the attribution. The Python
and Rust packs declare it in `pyproject.toml` and `Cargo.toml`; a Go module has
no licence field, so for the Go pack the `LICENSE` file is the declaration.
