# wrench, the project

Reads, writes and validates the form of the ecosystem's structured files. The
schemas live here, and a library per language that handles one.

## What it is FOR

Every component here reads and writes YAML that another component has to
understand. bolt writes a result envelope, a checker reads a jig, an adapter
writes a manifest. Without one place owning the form of those files, each
component grows its own reader, its own emitter and its own idea of what a valid
envelope is, and they drift while all of them believe they conform.

So wrench owns the contract and everything else is a consumer. No consumer's
convenience settles what the contract is, which is why the contract is specified
before any pack is written and why the schemas are one copy instead of one per
language.

It establishes that a file has the form its schema declares, and stops. What a
jig's keys mean and what an envelope's reasons say belong to the components that
produce and consume them.

## Where to read what

    docs/SPEC.md          how the pieces fit: the two calls, the seams, the
                          error kinds, canonical form, the schema rules
    docs/REQUIREMENTS/    the contract, one file per requirement, and its
                          README explains retirement and the status markers
    docs/DECISIONS/       why the project is shaped as it is
    docs/PATTERNS/        the shape to follow when changing something
    docs/LESSONS/         what a mistake here cost
    NEXT_STEPS.md         open questions and context that is not yet work

`docs/SPEC.md` is written so a fourth pack can be built from it, and it names
what it does not specify. Read it before this file if the question is how
something works; read this file for how the project is run.

The work itself is not in this repository. `clank/tasks/wrench/` holds it and
`clank/inbox/wrench/` holds findings filed by other sessions.

## Layout

    schemas/                 the schemas, one copy, read by every pack
    testdata/canonical/      the shared fixture set holding the packs level
    testdata/checkers/       tests for wrench's own checkers
    testdata/consumer/       a typed consumer, type-checked and never run
    bin/                     wrench's own checkers, and two symlinks into
                             toolbox that change behaviour here with nothing
                             in this repository moving
    adapters/                one symlink into toolbox, the composition adapter,
                             resolved from the config directory like any other

    wrench.go codec.go       the Go pack, at the repository root
    file.go schema.go        shipped_gen.go is generated from schemas/
    errors.go yaml.go
    json.go toml.go
    *_test.go

    python/wrench/           the Python pack
    python/tests/            _shipped.py is generated from schemas/

    rust/src/                the Rust pack
    rust/tests/              build.rs generates its copy every build

The Go pack is at the root and the other two are under their own directories.
That asymmetry is known: `clank/tasks/wrench/gate/05` holds why the move is
deferred rather than open.

## The gate

    bolt wrench-quality .

**Read `success` in `result.yaml`. Never the exit status.** bolt exits 0
whenever the run completed, whatever the tools concluded, and says so in its own
usage.

**Nor the summary line, which is a third thing and is wrong.** Its last line of
stdout labels the total execution count with the run's verdict, so `failed: 27`
and `passed: 27` count the same 27 executions.

**Read the per-task artifacts too**, because a nested run's failure is a level
down:

    grep '^"success"' <output-dir>/result.yaml
    grep -rln 'success": false' <output-dir>/

**Give it a fresh `--output-dir`.** bolt refuses a directory that already holds
a run, and **the two builds differ in what the refusal costs.**

The Go build, which is what `bolt` resolves to today and what `bolt.go` always
names, rewrites the earlier
`result.yaml` while refusing. Measured against a run that passed: `success` went
from `true` to `false` and the checksum changed, with all 28 execution
directories still in place. So the refusal replaces a real verdict with a record
of itself.

The Rust build preserves it, by FR-2.6b and FR-10.7c and a test named for it,
confirmed by the bolt session against a freshly built binary.

Measure this against a jig that **passes**. A run that refused for some other
reason never wrote a verdict, so a second refusal looks like an overwrite and is
two refusals in a row. Compare by checksum: both writes land inside one second
and mtime reports the file unchanged.

Filed at `clank/inbox/bolt.go/a-refusal-overwrites-the-run-it-refused`, which
also carries a race between two runs starting in the same second. Do not file it
again. bolt.go gets no agent by our user's ruling, so the fix is the cutover;
what the entry is for is stopping anybody writing a recipe with a fixed
`--output-dir` before the symlink moves, since that is the ordinary way to write
one and it triggers this every run.

**Analysis never scans an output or artefact directory.** The jig defines
`artefacts_regex` once and the tasks that need it filter with it: every
dot-directory, anything named for a cache, and build, dist, out and target. A
scratch `.go` file under `.ephemera` used to fail `go-format`, and a stale
`python/build/` still fails the shared Python jig's mypy and pylint, filed
against toolbox.

Two lines are silenced and nothing is mocked. `SUPPRESSIONS` carries both with
the question asked and the answer given, and `suppressions-everywhere` checks
the register against every source file rather than only the Python pack. There
is no `docs/MOCKS/`; that directory is claimed when something needs it.

### Check which bolt you ran before quoting what bolt does

Two implementations exist and they differ in what a refusal costs. **Each has a
name**, so a claim about bolt can say which one it is about:

    bolt        whichever build bin/bolt points at
    bolt.go     the Go build, always

`bolt` is the Rust build, since `dotfiles 19df074`. `bolt.go` stays installed
and keeps naming the Go implementation, so a claim about either can still be
checked rather than remembered.

**`bin/bolt` is an installed artefact and nothing rebuilds it.** Change bolt,
skip the reinstall, and every gate in the estate runs the old binary and passes.
That is the shape `a-check-that-answers-a-weaker-question` describes, at the
scale where it costs something.

    ls -la ~/bin/bolt ~/bin/bolt.go

**Both builds run this gate, 28 executions each**, measured 2026-08-29. Nested
jigs are retired at bolt `f3304d8` and this jig holds none: `python-common` and
`python-std` are command tasks whose program is bolt, each giving its child a
`{work_dir}/child` of its own.

**`adapters/common/bolt-result.py` is what lets a composed task fail.** bolt
exits 0 whenever it carried a run out, so under the generic exit-code adapter
the parent passes however badly the child failed. toolbox measured one failing
child both ways, `success=True` without it and `success=False` with it. A ruff
error planted inside `python/` surfaces here as the parent's own reason, keeping
the child's `kind` and `message` and naming the child result it came from.

Write the flags before the positionals. The Go build prints usage to stderr and
exits 1 otherwise, which reads as the adapter being wrong; the Rust build takes
either order.

## The packs

| Pack | Serves | State |
|---|---|---|
| Go | `bolt.go`, the previous Go implementation | Built, at the repository root |
| Python | toolbox's adapters and checkers | Built, under `python/` |
| Rust | bolt, which is now a Rust implementation | Built, suite level with the others |
| TypeScript | Consumer not yet identified | Not built |
| Ruby | Consumer not yet identified | Not built |

`packs-follow-demand` says what decides when a pack gets written, and it is a
consumer rather than a library.

**Bump the pack version in the same commit as a change to its surface.** uv
resolves from its cache by version, so an unchanged number is a package it
already has. Eight commits of change shipped under one version before a consumer
noticed receiving none of it.

## What holds the packs level

The shared fixture set in `testdata/canonical/`, plus the same tables asserted
in every suite. No pack is the oracle for another: if they disagree, the fixture
is right.

A fixture set proves agreement only over the values it holds, and a gap in it
looks exactly like agreement. That is not a closed defect but the standing
caution; `a-fixture-set-agrees-about-the-values-somebody-thought-of` carries
what it cost, and boundary cases are derived from each type instead of from
imagination.

Divergence between the suites is declared rather than accidental, and the scope
marker on a requirement row is the only place it is declared. A scope may name
kinds as well as suites, which is what `FR-4.1` needs: every pack covers it for
`property` and only two can construct its `edge` and `negative` values.

**Regenerate that rather than trusting this paragraph.**
`bin/test-suite-parity.py` names every divergence and exits non-zero when it
finds an undeclared one:

    ./bin/test-suite-parity.py --requirements docs/REQUIREMENTS \
        --suite go='*_test.go' --suite python='python/tests/*.py' \
        --suite rust='rust/tests/*.rs' . ; echo $?

`docs/PATTERNS/holding-two-packs-level.md` is what keeps it this way. Assert the
same table in every suite; a table that differs is packs that differ. Its name
predates the third pack.

## How it fits against its siblings

**bolt** is the Rust implementation and takes the Rust pack by path, so an
uncommitted change under `rust/` is bolt's build. The `bolt` this gate executes
is the Go one, a deliberate bridge kept while bolt is rebuilt.

**toolbox** owns the shared jigs and the checkers `bin/` symlinks into. A change
there lands here with nothing in this repository moving, which has turned the
gate red on rows nothing had previously read. toolbox's adapters are the Python
pack's intended consumer.

**silo** owns the platform decision wrench implements, that every structured
file is YAML validated as JSON Schema over the decoded structure. wrench does
not make that decision and does not get to differ from it.

**skid** consumes the Python pack and is the first caller to type-check against
it, which found the public API annotated more narrowly than it behaves.

A consumer enforces the schema it was built with rather than the one shipped
here, and nothing in this repository can detect the gap.
`a-consumer-enforces-the-schema-it-was-built-with` explains why no guard here
could.

## What is not done

`clank/tasks/wrench/` is the register and `NEXT_STEPS.md` carries the open
questions. In summary: the Go and Rust packs have no shared-standard base of
their own, the Go pack is at the root rather than under `go/`, and the
documents have not all been swept to the writing standard.

There is no git remote, which is the expected state across this ecosystem while
the history rewrite settles. Re-adding one is not this project's call.
