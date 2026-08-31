# Every pack compiles the schemas in, and a gate task holds the copy honest

## The decision

`schemas/` is the one copy. Each pack carries those bytes as source, generated
from the directory rather than written by hand.

    Go      go/shipped_gen.go  bin/generate-shipped.py, committed
    Python  _shipped.py        bin/generate-shipped.py, committed
    Rust    shipped.rs         build.rs, regenerated every build

A pack resolves its schemas without reference to where it was installed.

## Why not read them from disk

The Python pack used to, by walking two directories up from `__file__`. That
made an editable install the only supported form, which is what hid `py.typed`
from mypy and cost a consumer an hour: an editable install exposes the package
through an import hook, and mypy resolves statically and cannot follow one.

Compiling them in also gives Go and Rust the single static binary FR-3.5 permits
and bolt wants.

## Why generated rather than `//go:embed`

`//go:embed` cannot reach above its own package. A `../` pattern is invalid
pattern syntax and a symlink is an irregular file, both measured, so an
embedding package is pinned to the directory holding the schemas forever. That
scoping was the whole of what blocked moving the Go pack under `go/`.

Generation has no such limit, and Rust already needed it because it has no
directory embed in the standard library.

## What it costs, and what makes the cost safe

Two committed second copies of every schema, which is the drift FR-3.2 exists to
prevent.

The gate task `shipped-schemas-are-current` runs the generator with `--check`,
comparing bytes against a fresh run. It catches an edited schema, an added one,
a removed one and a hand-edited generated file alike, and each was verified by
breaking the tree that way rather than by reading the code. Rust has no such
task because `build.rs` runs on every build and its copy cannot go stale.

Without that check this would be a second copy of every schema with nothing
watching it, which is worse than reading from disk. The check is the whole
reason the trade is acceptable.

## What it does not change

FR-3.7 still holds: a pack finds the schemas by reading the directory, never
from a list a person maintains. No compiler here can read a directory, so the
reading happens in a generator. Adding a schema to `schemas/` reaches every pack
without anybody editing a source file.
