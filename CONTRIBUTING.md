# Contributing

wrench owns one definition of what a structured file may contain, and four
libraries that hold to it. A change is accepted when they still agree, so most
of what follows is about keeping them level.

Read `docs/SPEC.md` first if the question is how something works. It is written
so that another pack could be built from it, and it names what it does not
specify.

## Layout

    schemas/                 the schemas, one copy, read by every pack
    testdata/canonical/      the shared fixture set that holds the packs level
    bin/                     the repository's own checkers

    go/                      the Go pack
    python/wrench/           the Python pack
    rust/src/                the Rust pack
    ruby/lib/wrench/         the Ruby pack

## Running the suites

    (cd go && go test ./...)
    PYTHONPATH=python python3 -m pytest python/tests -q
    cargo test --manifest-path rust/Cargo.toml
    (cd ruby && ruby -Ilib -Itest test/test_wrench.rb)

`just test` delegates to each pack that has adopted its own Justfile. Run the Go
suite from `go/` until that pack adopts one, and the Ruby suite by hand: `PACKS`
in the `Justfile` names go, python and rust, so `just test` compiles nothing
Ruby and reports nothing about it.

The Python suite needs `PyYAML`, `jsonschema` and `referencing` importable. The
pack imports them by name, so a platform package satisfies it as well as a
resolver does, and it runs from a source checkout with no install having
happened.

The Ruby suite needs `json_schemer` and `minitest`. Psych and `json` are
standard library and the pack declares neither, because they are the emitters
and the pack adds only the adapters on top of them.

## The parity check

Every pack's suite covers the same cases, and this is what fails when one does
not:

    ./bin/test-suite-parity.py --requirements docs/REQUIREMENTS \
        --suite go='go/*_test.go' --suite python='python/tests/*.py' \
        --suite rust='rust/tests/*.rs' .

A divergence is possible and has to be declared. The scope marker on a
requirement, such as `[python]`, is the only authority on which packs are
expected to discharge that row, and nowhere else holds a second copy of that
list.

Adding a scope marker to silence a parity failure is the one wrong use of it. A
marker is for a row a pack cannot discharge; a row merely untested in one pack
is the finding.

**The Ruby pack is not in that command.** Adding `--suite
ruby='ruby/test/*.rb'` reports 55 divergences and exits 1, because the pack is
new and its suite covers 16 rows against the 67 the other three hold level.
Neither a scope marker nor a deletion is the answer there: the tests are missing
and have to be written.

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

A change to what one pack emits is a change to every pack, and to the fixture
set in `testdata/canonical/`. If two packs disagree, the fixture is right; no
pack is the oracle for another.

What has to agree is the value, not the bytes. Any pack's output must decode to
the same thing in every other pack, and a difference in indentation or line
wrapping is not a defect. What is a defect is a difference a reader can see: a
key that was a string coming back as a number, a float spelled with an exponent,
a null that reads as the empty string. Those four properties are the adapters
`docs/SPEC.md` lists, and they are what a change here has to preserve.

Emit through the language's library with those adapters on top. A hand-written
emitter is what byte-identity used to force, it is where the defects turned up,
and two packs still carry one. `packs-agree-on-structure-not-on-bytes` is the
argument and `adopting-a-library-for-a-codec` is the procedure.

Parity is reached by widening. Where the packs differ, the one that handles more
is right and the others learn from it, and agreement bought by accepting less
counts here as a failure.

A schema added to or edited in `schemas/` reaches Go and Python through a
generated file that is committed:

    ./bin/generate-shipped.py            write the generated files
    ./bin/generate-shipped.py --check    exit 1 if any is stale, and say which

Rust needs neither, `rust/build.rs` regenerating its copy on every build. Ruby
carries no copy and reaches no schema of its own, so a schema change does not
reach that pack at all.

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

    ln -sf ../../bin/githooks/pre-commit .git/hooks/pre-commit.local

Git consults exactly one hooks directory. If `git config --get core.hooksPath`
prints a path, that directory is the only one git reads and a hook under
`.git/hooks/` never runs: no error, no warning, and the only way to learn it is
inert is to watch it fail to refuse something. Where a hook there dispatches to
a per-repository one, install to the name it dispatches to instead.

## The full gate, and why it is not inside this repository

The suites and the parity check are what a contributor runs, and they need
nothing but this checkout.

Beyond them, this repository is held to a **quality standard versioned in one
place and adopted by every project that uses it**. The checkers, the adapters
and the tool configuration live in a companion repository, `toolbox`, and a
project adopts them as symlinks rather than as copies. One definition of what a
passing repository looks like, changed once, and every adopter has the change.

That is the same argument this project makes about file formats: several
implementations of one standard drift, and the fix is to give the standard a
single owner. wrench owns the format; toolbox owns the gate.

**The cost is that a clone of this repository alone has no gate.** The links
point at a sibling that is not there yet, so the runner reports a definition it
cannot read. That is adoption not yet run, rather than a broken checkout.

Clone `toolbox` beside this repository and run its linker:

    git clone https://github.com/scriptedworld/toolbox.git ../toolbox
    python3 ../toolbox/bin/link-toolbox.py --yes . go python

`go` and `python` are the sets wrench adopts. `go` pulls in `common`, and
`common` pulls in `secrets`, so those two names bring twelve links. To verify an
adoption rather than make one:

    $ python3 ../toolbox/bin/link-toolbox.py --check . go python
    all 12 link(s) present and correct

`--check` writes nothing and exits 1 on any drift, so it is safe to run first,
and `--plan` says what would happen and stops.

The gate itself is `bolt`, a runner that reads a quality definition and runs the
checkers it names:

    bolt wrench-quality .

Two things to know when you run it. **Read `success` in the `result.yaml` it
writes and never the exit status**, which is 0 whenever a run was carried out at
all, whatever the tools concluded. And give it an output directory that does not
already hold a run, because it refuses one that does.

## Commits and prose

Conventional commits, one concern per commit. The subject says what changed. The
body says what it cost, in figures a reader of the log cannot get without
running the suite, and leaves the reasoning in the file the commit changed.

Documentation here is evergreen. It states what is true now and leaves the
history to git, so a statement carries no date and no record of what the
document used to say. Where a mistake is instructive it goes in `docs/LESSONS/`
as a lesson, written once.
