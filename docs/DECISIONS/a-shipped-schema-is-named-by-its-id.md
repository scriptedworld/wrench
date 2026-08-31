# A shipped schema is named by its `$id`, and they reference each other by it

## The decision

Every shipped schema declares an `$id`. That identifier is what it is called in
an error, what another schema references it by, and what a pack looks it up by.
A filename is an implementation detail of where it happens to sit on disk.

Before any shipped schema compiles, **all** of them are registered under their
declared `$id`, so a `$ref` from one to another resolves locally.

## Why the id and not the filename

A relative filename resolves against whatever directory the process happened to
start in. That put an absolute local path into a validation error, and a
validation error travels inside an envelope as evidence, to be read on another
machine by someone who has never seen that directory.

That was a real defect, not a hypothetical. Both packs carry a regression test
that the error names `scriptedworld.github.io/wrench/...` and does not contain
the repository root.

## Why they must reference each other

A definitions mapping is one shape whether it is a jig's own `definitions` block
or a file supplying them. Written twice, the two copies are free to drift, and
nothing would report it. So `jig.schema.json` points its `definitions` property
at `definitions.schema.json` by `$id` instead of restating the shape.

The test that proves the reference resolved is the one where a jig carrying a
**nested** definitions value is refused. `jig.schema.json` states no such rule
itself, so a refusal can only have come from the referenced schema.

## Read the directory, do not list the filenames

A pack discovers the shipped schemas by reading `schemas/`, not from a list of
filenames kept in its source.

This is not a style preference. The Python pack named three
files in `schema.py` while Go read the directory. A fourth schema was added, Go
picked it up and Python did not, and the divergence was invisible until something
validated a document that used it. Reading the directory removes the step where
adding a schema means remembering a second place.

## Where it is implemented

`go/schema.go`, `compileShipped` and `readShipped`. `python/wrench/schema.py`,
`_shipped_documents` and `_shipped_registry`.
