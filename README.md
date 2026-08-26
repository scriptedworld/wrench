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

The envelope is one schema and a jig is another. YAML everywhere, validated as
JSON Schema over the decoded structure, written in canonical form.

A library per language rather than a C core with bindings: the codecs are the
easy half, and C has nothing comparable to Go's or Python's JSON Schema
implementations. Independent implementations agreeing is what the specification
and its cross-implementation test suite are for.

Language packs follow demand. Go serves bolt, Python serves toolbox's adapters
and checkers, and the next waits until something needs it. The contract is
settled first and specified independently of any implementation, so a later pack
is written from the contract rather than by reading the Go one.

The contract is stated in `REQUIREMENTS.md`, derived from those decisions and
from
`silo/docs/DECISIONS/yaml-everywhere-validated-against-the-decoded-structure.md`,
where the platform decision now lives.

Nothing is built yet.
