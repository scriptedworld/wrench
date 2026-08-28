# wrench

Reads, writes and validates the form of the ecosystem's input and output files.
The schemas live here, and a library for each language that handles one, so a Go
producer and a Python producer work from the same definition rather than from
two implementations obliged to keep up with each other.

Two calls:

    load_formatted_file(path, schema, codec, reader)
    save_formatted_file(data, path, schema, codec, writer)

Validation is in the signature, so nothing reads or writes without naming what
the file must conform to. The codec is the format and the reader or writer is
the IO, declared separately, which puts the IO boundary outside the call and
lets a test exercise the validation paths against no filesystem.

Four schemas ship: the result envelope, a jig, a manifest, and the definitions a
jig's placeholders stand for. YAML everywhere, validated as JSON Schema over the
decoded structure, written in canonical form.

A library per language rather than a C core with bindings: the codecs are the
easy half, and C has nothing comparable to Go's or Python's JSON Schema
implementations. Packs follow demand, so a language gets one when something
needs to read or write a structured file in it.

## The packs

Go, at the repository root. Serves bolt.

    import "github.com/scriptedworld/wrench"

    envelope, err := wrench.LoadFormattedFile(
        path, wrench.EnvelopeSchema, wrench.YAML, wrench.LocalFile)

Python, under `python/`. Serves toolbox's adapters and checkers.

    from wrench import load_formatted_file, ENVELOPE_SCHEMA, YAML, LOCAL_FILE

    envelope = load_formatted_file(path, ENVELOPE_SCHEMA, YAML, LOCAL_FILE)

**Install the Python pack editable.** It reads the schemas from `schemas/` at the
repository root, so a copied install looks for files that are not beside it.

    uv pip install -e python/

What holds the two level is the shared fixture set in `testdata/canonical/`.
Neither pack is the oracle for the other: if they disagree, the fixture is right.

## Reading further

`docs/REQUIREMENTS/` is the contract, one file per requirement, derived from this README, from bolt's rows
stating the contract rather than its use of it, and from
`silo/docs/DECISIONS/yaml-everywhere-validated-against-the-decoded-structure.md`,
where the platform decision lives.

`docs/PROJECT.md` is what a session needs before changing anything here, and
`docs/DECISIONS/` says why the project is shaped as it is. Before touching a
schema or adding a pack, read `docs/PATTERNS/holding-two-packs-level.md`.

    go test ./...
    PYTHONPATH=python python3 -m pytest python/tests -q

## Licence

Apache-2.0. `LICENSE` carries the terms and `NOTICE` the attribution; both packs
declare it in their own manifests, so the three cannot drift apart silently.
