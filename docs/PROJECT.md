# wrench, the project

Reads, writes and validates the form of the ecosystem's structured files. The
schemas live here, and a library per language that handles one.

## What it is FOR

Every component here reads and writes YAML that another component has to
understand. A runner writes a result envelope, a checker reads a jig, an adapter
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

    README.md             what wrench is, for somebody arriving cold
    CONTRIBUTING.md       how to build it, test it, and get a change accepted
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

## Layout

    schemas/                 the schemas, one copy, read by every pack
    testdata/canonical/      the shared fixture set holding the packs level
    testdata/checkers/       tests for wrench's own checkers
    testdata/consumer/       a typed consumer, type-checked and never run
    bin/                     wrench's own checkers, beside two links into
                             toolbox that change behaviour here with nothing
                             in this repository moving
    adapters/ config/        adopted from toolbox, all links and none tracked

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
That asymmetry is known and the move is deferred work rather than an open
question.

## The gate

    bolt wrench-quality .

Read `success` in `result.yaml`, never the exit status. bolt exits 0 whenever
the run completed, whatever the tools concluded, and says so in its own usage.

Read the per-task artifacts too, because a composed run's failure is a level
down:

    grep '^"success"' <output-dir>/result.yaml
    grep -rln 'success": false' <output-dir>/

Give it an output directory that does not already hold a run. bolt refuses one
that does, and a refusal is not a verdict about the code.

`adapters/common/bolt-result.py` is what lets a composed task fail. bolt exits 0
whenever it carried a run out, so under the generic exit-code adapter a parent
passes however badly its child failed. With the adapter in place, a checker
error inside `python/` surfaces here as the parent's own reason, keeping the
child's `kind` and `message` and naming the child result it came from.

Analysis never scans an output or artefact directory. The jig defines
`artefacts_regex` once and the tasks that need it filter with it: every
dot-directory, anything named for a cache, and build, dist, out and target. A
scratch `.go` file under `.ephemera` used to fail `go-format`, and a stale
`python/build/` still fails the shared Python jig's mypy and pylint.

Two lines are silenced and nothing is mocked. `SUPPRESSIONS` carries both with
the question asked and the answer given, and `suppressions-everywhere` checks
the register against every source file, not only the Python pack. There is no
`docs/MOCKS/`; that directory is claimed when something needs it.

## The packs

| Pack | Serves | State |
|---|---|---|
| Go | bolt's Go implementation | Built, at the repository root |
| Python | toolbox's adapters and checkers | Built, under `python/` |
| Rust | bolt | Built, suite level with the others |
| TypeScript | Consumer not yet identified | Not built |
| Ruby | Consumer not yet identified | Not built |

`packs-follow-demand` says what decides when a pack gets written, and it is a
consumer, not a library.

Bump the pack version in the same commit as a change to its surface. A resolver
serves an unchanged version number out of its cache, so a consumer receives none
of the change. Eight commits of change shipped under one version before a
consumer noticed receiving none of it.

## What holds the packs level

The shared fixture set in `testdata/canonical/`, plus the same tables asserted
in every suite. No pack is the oracle for another: if they disagree, the fixture
is right.

A fixture set proves agreement only over the values it holds, and a gap in it
looks exactly like agreement. That is the standing caution rather than a closed
defect; `a-fixture-set-agrees-about-the-values-somebody-thought-of` carries what
it cost, and boundary cases are derived from each type instead of from
imagination.

Divergence between the suites is declared, never accidental, and the scope
marker on a requirement row is the only place it is declared. A scope may name
kinds as well as suites, which is what `FR-4.1` needs: every pack covers it for
`property` and only two can construct its `edge` and `negative` values.

Regenerate that instead of trusting this paragraph.
`bin/test-suite-parity.py` names every divergence and exits non-zero when it
finds an undeclared one:

    ./bin/test-suite-parity.py --requirements docs/REQUIREMENTS \
        --suite go='*_test.go' --suite python='python/tests/*.py' \
        --suite rust='rust/tests/*.rs' .

`docs/PATTERNS/holding-two-packs-level.md` is what keeps it this way. Assert the
same table in every suite; a table that differs is packs that differ. Its name
predates the third pack.

## How it fits against its siblings

**bolt** takes the Rust pack by path, so an uncommitted change under `rust/` is
bolt's build. It is also what runs this repository's gate.

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

`NEXT_STEPS.md` carries the open questions. In summary: the Go and Rust packs
have no shared-standard base of their own, the Go pack is at the root instead of
under `go/`, and the prose sweep has had no validator pass, which by its own
design cannot be the writer.
