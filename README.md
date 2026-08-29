# wrench

**One definition of what a structured file may contain, and a library in each
language that holds to it.**

When several programs read and write the same file, each one grows its own
reader, its own emitter, and its own idea of what a valid document is. They
drift, and every one of them believes it conforms. wrench exists so there is one
place that owns the answer.

A **pack** is the library for one language. Three ship — Go, Python and Rust —
and they are not ports of each other: each binds its own JSON Schema validator
and parsers, and each is written from the same written contract. What makes them
one library rather than three is a property that is tested rather than intended.

## The guarantee

**The same document, through any pack and any codec, produces the same bytes.**

That sounds obvious and is not. Standard libraries disagree about how to spell
ordinary values, quietly, in ways that survive every test until a consumer
notices:

| value | Go | Python | Rust |
|---|---|---|---|
| `1000000.0` | `1e+06` | `1000000.0` | `1000000.0` |
| `1e21` | `1e+21` | `1e+21` | `1000000000000000000000.0` |

Those were wrench's own three packs. The defect was found from outside, by a
program whose display matched `[0-9.]+` against the value and so read `1e+06` as
**1** — a count of a million shown as one, across a repository boundary, with no
error anywhere.

Every pack now writes a float the same way: positional decimal, never an
exponent, shortest digits that read back identically. The rule carries no
threshold, because every alternative needs a magnitude at which the spelling
changes, and that number then has to be implemented identically in nine places.

The same applies to control characters. A raw one in a quoted YAML scalar is
refused by a strict reader, accepted by a lenient one, and silently folded to a
space by a third, so a file carrying one has no single meaning. Every pack
escapes it, in each format's own spelling, and no value is refused for carrying
one.

**Parity is reached by widening, never by narrowing.** Where the packs disagree,
the one that handles more is right and the others learn from it. Restricting what
wrench accepts so that the packs agree by handling less is the outcome the
project treats as a failure.

## The two calls

    load_formatted_file(path, schema, codec, reader)
    save_formatted_file(data, path, schema, codec, writer)

**Validation is in the signature**, so nothing reads or writes without naming
what the file must conform to. There is no unvalidated path to fall into.

**The codec and the IO are separate arguments**, which puts the filesystem
outside the call: a test substitutes a reader and exercises every validation path
against no disk at all.

Four schemas ship — a result envelope, a jig, a manifest, and the definitions a
jig's placeholders stand for — and a caller may pass its own. They are ordinary
JSON Schema files, validated against the decoded structure, so a YAML document is
held to a JSON Schema without either format needing to know about the other.

## The packs

**Go**, at the repository root.

    import "github.com/scriptedworld/wrench"

    envelope, err := wrench.LoadFormattedFile(
        path, wrench.EnvelopeSchema, wrench.YAML, wrench.LocalFile)

**Python**, under `python/`.

    from wrench import load_formatted_file, ENVELOPE_SCHEMA, YAML, LOCAL_FILE

    envelope = load_formatted_file(path, ENVELOPE_SCHEMA, YAML, LOCAL_FILE)

Install it editable — it reads the schemas from `schemas/` at the repository
root, so a copied install looks for files that are not beside it:

    uv pip install -e python/

**Rust**, under `rust/`.

    use wrench::{load_formatted_file, ENVELOPE_SCHEMA, YAML, LOCAL_FILE};

    let envelope = load_formatted_file(path, &ENVELOPE_SCHEMA, &YAML, &LOCAL_FILE)?;

Each spells the calls the way its language spells things; what the packs share is
behaviour, not identifiers. The decoded value is that language's natural shape
for JSON — `map[string]any`, `dict`, `serde_json::Value` — so nothing converts
between validating and returning.

A library per language rather than a C core with bindings: the codecs are the
easy half, and C has nothing comparable to the JSON Schema implementations these
languages already have. A language gets a pack when something needs to read or
write a structured file in it.

## Errors

**Every failure that crosses the boundary is wrench's own type**, whatever the
library underneath raised. A consumer catching a parse failure should not have to
know whether wrench binds PyYAML or something else; if the bound library were
visible in the error type, swapping it would break every consumer.

    ReadError        the file could not be read at all
    ParseError       the bytes are not the format they were read as
    ValidationError  the structure parsed and does not match its schema
    EncodeError      a value has no canonical form in this codec
    WriteError       the bytes could not be put in place
    SchemaError      the schema itself will not compile

The cause is always preserved — Python `__cause__`, Go `errors.Unwrap`, Rust
`source()` — so a caller who wants the underlying error can still reach it. A
wrap that discarded it would be worse than a leak.

**Python, changing in 0.1.0: these no longer derive from `ValueError`.** They
derive from `WrenchError`, which derives from `Exception`. Code written as

    except ValueError:          # catches nothing from wrench now

silently stops catching, and an uncaught validator looks exactly like a passing
one from anywhere except a test on the refusal path. Catch `wrench.WrenchError`,
or the specific type. Found by a consumer whose refusal tests went red the moment
it landed; those tests are the reason it was noticed rather than deployed.

## Three formats

    load_yaml_file  save_yaml_file
    load_json_file  save_json_file
    load_toml_file  save_toml_file

The codec is named rather than guessed from the file extension, because choosing
a parser by filename makes behaviour depend on what a file is called.

**Every save writes canonical form.** Keys are sorted, layout is fixed, and
comments do not survive a load. That is the point rather than a limitation: two
producers of the same structure emit the same bytes, which is what stops
components drifting while all of them believe they conform.

**So wrench is the wrong writer for a file a person edits.** A config with
comments and a deliberate entry order goes in and comes out reordered and
stripped. Reach for a round-trip-preserving editor there, such as `tomlkit` in
Python, and use wrench for the read half: decoding and validating against a
schema is the larger win, and it is where a config file is usually unchecked.

**Machine-written files are what canonical form is for.** Envelopes, jigs,
manifests, queue entries. Nobody has typed a note into one, the ordering carries
no meaning, and byte-identical output between producers is worth having.

## What holds the packs level

A shared fixture set in `testdata/canonical/`, read by all three suites. **No
pack is the oracle for another**: if they disagree, the fixture is right.

`bin/test-suite-parity.py` checks that every requirement tested in one suite is
tested in all of them, and fails when it is not. Divergence is possible but has
to be declared and reasoned for, not merely allowed to happen.

That check earned itself. It began at seven requirements the Go pack tested
alone, and a schema change once landed green in Go because the only test of that
schema lived in the Python suite.

**A fixture set only proves agreement over the values it holds**, which is the
lesson both defects above taught. Boundary cases are derived from the type rather
than chosen by hand.

## Reading further

`docs/REQUIREMENTS/` is the contract, one file per requirement. Every test names
the requirement it discharges, and a checker fails the build if a test cites
nothing or cites something that does not exist.

`docs/DECISIONS/` says why the project is shaped as it is, and `docs/LESSONS/`
what a mistake here cost. `docs/PROJECT.md` is what to read before changing
anything.

    go test ./...
    PYTHONPATH=python python3 -m pytest python/tests -q
    cargo test --manifest-path rust/Cargo.toml

## Licence

Apache-2.0. `LICENSE` carries the terms and `NOTICE` the attribution.

The Python and Rust packs also declare it in `pyproject.toml` and `Cargo.toml`,
so a consumer resolving either through a package index sees it without reading
the tree. A Go module has no licence field, so for the Go pack the `LICENSE` file
is the declaration.
