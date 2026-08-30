# Contributing

wrench owns one definition of what a structured file may contain, and three
libraries that hold to it. A change is accepted when the three still agree, so
most of what follows is about keeping them level.

Read `docs/SPEC.md` first if the question is how something works. It is written
so that a fourth pack could be built from it, and it names what it does not
specify.

## Layout

    schemas/                 the schemas, one copy, read by every pack
    testdata/canonical/      the shared fixture set that holds the packs level
    bin/                     the repository's own checkers

    *.go                     the Go pack, at the repository root
    python/wrench/           the Python pack
    rust/src/                the Rust pack

The Go pack sits at the root while the other two have a directory each. That
asymmetry is known, and moving it is deferred work rather than an open question.

## Running the suites

    go test ./...
    PYTHONPATH=python python3 -m pytest python/tests -q
    cargo test --manifest-path rust/Cargo.toml

`just test` delegates to each pack's own Justfile and runs the Python and Rust
suites. It does not run the Go suite: the delegator looks for `go/Justfile`, the
Go pack is at the root, so `go` is reported as not adopted and skipped and the
command exits 0 having compiled no Go at all. Run `go test ./...` yourself.

The Python suite needs `PyYAML`, `jsonschema` and `referencing` importable. The
pack imports them by name, so a platform package satisfies it as well as a
resolver does, and it runs from a source checkout with no install having
happened.

## The parity check

Every pack's suite covers the same cases, and this is what fails when one does
not:

    ./bin/test-suite-parity.py --requirements docs/REQUIREMENTS \
        --suite go='*_test.go' --suite python='python/tests/*.py' \
        --suite rust='rust/tests/*.rs' .

A divergence is possible and has to be declared. The scope marker on a
requirement, such as `[python]`, is the only authority on which packs are
expected to discharge that row, and nowhere else holds a second copy of that
list.

Adding a scope marker to silence a parity failure is the one wrong use of it. A
marker is for a row a pack cannot discharge; a row merely untested in one pack
is the finding.

## Every test names its requirement

    // COVERS: FR-2.1, FR-2.2 | positive

Go and Rust write it with `//`, Python with `#`, in the comment block
immediately above the test. Rust must use `//` and never `///`, because a doc
comment does not match the pattern and the test then reads as carrying no
annotation at all instead of failing loudly.

The kinds are `positive`, `negative`, `edge`, `property` and `regression`. A
test citing nothing fails the check, so does a test citing a requirement
`docs/REQUIREMENTS/` does not define, and so does a settled requirement with no
test at all.

`docs/REQUIREMENTS/` holds one file per requirement, and its README explains the
status markers and how retirement works. A requirement id is never reused.
Retiring one renames its file to a `.retired` suffix, and the `COVERS:` marks
pointing at it are repointed or removed in the same change.

## Changing what a pack emits

A change to what one pack emits is a change to all three, and to the fixture set
in `testdata/canonical/`. If two packs disagree, the fixture is right; no pack
is the oracle for another.

Parity is reached by widening. Where the packs differ, the one that handles more
is right and the others learn from it, and agreement bought by accepting less
counts here as a failure.

A schema added to or edited in `schemas/` reaches Go and Python through a
generated file that is committed:

    ./bin/generate-shipped.py            write the generated files
    ./bin/generate-shipped.py --check    exit 1 if any is stale, and say which

Rust needs neither, `rust/build.rs` regenerating its copy on every build.

Bump the pack version in the same commit as a change to its surface. A resolver
serves an unchanged version number out of its cache, so a consumer receives none
of the change and nothing anywhere reports that.

## Suppressions

Do not add a `# nosec`, a `//nolint`, or anything else that silences a check,
without registering it in `SUPPRESSIONS` with the question that was asked and
the answer that was given. An entry there is the justification, not a record
that one was wanted. When a check fails the options are to fix it or to ask.

A hook refuses a commit carrying a pragma `SUPPRESSIONS` does not name. Install
it once per checkout:

    ln -sf ../../bin/githooks/pre-commit .git/hooks/pre-commit

Git consults exactly one hooks directory. If `git config --get core.hooksPath`
prints a path, that directory is the only one git reads and a hook under
`.git/hooks/` never runs: no error, no warning, and the only way to learn it is
inert is to watch it fail to refuse something. Where a hook there dispatches to
a per-repository one, install to the name it dispatches to instead.

## The full gate

The suites and the parity check are what a contributor runs. Beyond them the
repository is gated by bolt, a companion project that reads a quality definition
and runs the checkers it names. It is not published, so a change is gated when
it lands rather than in your checkout.

Two things to know if you do run it. Read `success` in the `result.yaml` it
writes and never the exit status, which is 0 whenever a run was carried out at
all. And give it an output directory that does not already hold a run, because
it refuses one that does.

## Commits and prose

Conventional commits, one concern per commit. The subject says what changed. The
body says what it cost, in figures a reader of the log cannot get without
running the suite, and leaves the reasoning in the file the commit changed.

Documentation here is evergreen. It states what is true now and leaves the
history to git, so a statement carries no date and no record of what the
document used to say. Where a mistake is instructive it goes in `docs/LESSONS/`
as a lesson, written once.
