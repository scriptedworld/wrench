# A C++ pack was built and removed

C++ gets no pack here, by direction. The code was written, passed its own gate,
and came out again.

## What it cost, which is the reason

The pack reached the codecs, the error family, the two calls, both wrappers per
format, the schema plumbing and its suite at roughly 3,200 lines, about a third
of it tests:

    cpp/src/yaml_codec.cpp     687
    cpp/tests/schema_test.cpp  378
    cpp/tests/codec_test.cpp   348
    cpp/src/schema.cpp         254
    cpp/src/json_codec.cpp     250
    cpp/tests/yaml_test.cpp    290
    cpp/tests/file_test.cpp    275
    cpp/CMakeLists.txt         135  plus 88 in cmake/generate-shipped.cmake

That is what a contract-conformant pack costs in this language, and it is more
than the contract buys here. The Go, Python, Rust and TypeScript packs each hold
the same contract for a fraction of the volume.

The size was not caused by a library being refused. libyaml was bound and used,
including its emitter, driven through the event API. The volume is that API's
verbosity plus the canonical form no library supplies: block style and quoting
that marks intent, one float spelling, control characters escaped, all of
FR-4.1 through FR-4.9 written out per codec.

## What it is not

Not a judgment that the design was wrong. The pack's own gate reported
`success: true`, its suite carried 113 `COVERS:` marks, and the three shape
decisions it made were sound enough to write down:

- the value type was `jsoncons::json` under `wrench::value`, because C++ has no
  value type every parser and validator agrees on, so a pack-owned tree would be
  converted on every call to arrive at the same values
- a failure was returned as `std::expected` with one error family, `usage` did
  not exist because the seams are references and a call naming none does not
  compile, and `std::bad_alloc` was the one thing still leaving through a throw
- CMake read `schemas/` on every build, so no committed copy could go stale,
  which is what `build.rs` buys Rust

Those are recorded here rather than kept as live decisions, because nothing in
the repository implements them any more.

## Where it went

`8cbeaf1` is the pack and `d36bafa` its decisions and the SPEC column, both
reachable from this line until the commit-message rewrite renumbers them. The
skeleton before them is `e16a406`, and `19b8bb0` and `3ed493d` carry the library
assessment and what the contract failed to answer for C++.

## What this does not settle

`packs-follow-demand` is unchanged: a pack is written when the estate writes
tools in that language. This decision says the answer for C++ was measured and
came out negative on cost, not that demand is the wrong test.

infobot's C++ rebuild was the stated consumer and has no pack now. Returning it
to its best existing implementation is infobot's work, dispatched through silo.
