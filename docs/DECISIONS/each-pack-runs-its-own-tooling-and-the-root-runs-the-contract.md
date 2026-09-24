# Each pack runs its own tooling, and the root runs the contract

## The decision

A pack's language tooling runs at that pack's base, through that pack's own
Justfile. The root runs what no pack can: the common standard over every file in
the repository, then wrench's own contract jig. `just checks` iterates the packs
and then runs both.

    cpp/Justfile          cpp-std-quality at cpp/
    go/Justfile           go-std-quality at go/
    python/Justfile       python-std-quality at python/
    rust/Justfile         cargo fmt, clippy, test, doc at rust/
    typescript/Justfile   prettier, eslint, tsc, node --test at typescript/

    Justfile              _each checks, then common-quality over the repository,
                          then wrench-quality

## Why, and it is not tidiness

One pack's leavings were graded as another's. The root jig ran `pytest
python/tests`, which wrote `.coverage` at the repository root beside
`python/.coverage`; `.gitignore` carried both paths, which is the fossil of it.
`gofmt -l go` walked trees Go's own `./...` skips, so the jig needed an
`artefacts_regex` to undo the reach. gcovr searches from its root, so any gcov
profile anywhere under the repository was read as the C++ pack's.

**A shared standard run at one pack's base reads one pack's share of the
repository.** `common-quality` ran at `python/`, so the wording check, the
secrets scan and the suppression register never opened `bin/`, `schemas/`,
`docs/`, or the Go, Rust, C++ and TypeScript packs. The first run at the root
found 22 wording errors in a pack nothing had ever read.

A contract check cannot run at a pack's base at all. A requirement scoped to
one pack has no test at another's, by design, so `traceability` at `rust/`
failed on rows Python is expected to discharge. The Rust pack's own `checks` had
been failing that way, unnoticed, because nothing ran it: the root jig ran
`cargo test` and `cargo fmt` directly and never called the pack's recipe.

## What follows from it

A pack that no recipe names is a pack that silently passes, so `PACKS` in the
root Justfile is the list that decides what runs, and a pack with no Justfile is
reported as skipped rather than quietly omitted.

The gate command is `just checks`, not `bolt wrench-quality .`. The jig alone
answers a narrower question than it used to, and says so in its own header.

Adding a pack is: its Justfile, its language jig adopted at its base, its name
in `PACKS`. Nothing at the root learns the pack's language.
