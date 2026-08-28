# wrench, the project

Reads, writes and validates the form of the ecosystem's structured files. The
schemas live here, and a library per language that handles one.

## What it is FOR

Every component here reads and writes YAML that another component has to
understand. bolt writes a result envelope, a checker reads a jig, an adapter
writes a manifest. Without one place owning the form of those files, each
component grows its own reader, its own emitter and its own idea of what a valid
envelope is, and they drift while all of them believe they conform.

So wrench owns the contract and everything else is a consumer. **No consumer's
convenience settles what the contract is**, which is why the contract is
specified before any pack is written and why the schemas are one copy rather than
one per language.

It establishes that a file has the form its schema declares, and stops. What a
jig's keys mean and what an envelope's reasons say belong to the components that
produce and consume them.

## The shape of the library

Two calls, the same in every pack:

    load_formatted_file(path, schema, codec, reader)
    save_formatted_file(data, path, schema, codec, writer)

Validation sits in the signature, so nothing reads or writes without naming what
the file must conform to. The codec is the format and the reader or writer is the
IO, declared separately, which puts the IO boundary wholly outside the call: a
test substitutes a reader and exercises the validation paths against no
filesystem at all.

The signature compels a schema, not the right one. Passing none is impossible;
passing the wrong one is not, and nothing here detects that.

## Layout

    REQUIREMENTS.md          the contract, one document every pack implements
    NEXT_STEPS.md            open questions and context that is not work
    schemas/                 the schemas, one copy, read by every pack
    testdata/canonical/      the shared fixture set holding the packs level
    bin/test-suite-parity.py the check that every pack's suite covers the same
                             tests. wrench's own, not a shared checker

    wrench.go codec.go       the Go pack, at the repository root
    file.go schema.go
    errors.go yaml.go
    *_test.go

    python/wrench/           the Python pack
    python/tests/
    python/pyproject.toml

    rust/src/                the Rust pack
    rust/tests/
    rust/Cargo.toml

    docs/DECISIONS/          why the project is shaped as it is
    docs/PATTERNS/           the shape to follow when working on X
    docs/LESSONS/            what a failure here cost

**The Go pack is at the root and the other two are under `python/` and `rust/`.**
That asymmetry is known and is a problem for the gate rather than for the code:
`clank/tasks/wrench/gate/05-move-the-go-pack-under-go.planning` wants the Go pack
moved to `go/` so the three are symmetric bases.

## The gate

    bolt wrench-quality .

2026-08-27: passes, 20 executions, `success: true` in `result.yaml`.
`bolt.wrench-quality.yaml` is wrench's own jig, eleven tasks over the schemas, the
packs and the contract.

**Read `result.yaml`, never the exit status.** bolt exits 0 whenever the run
completed, whatever the tools concluded, and says so in its own usage. The verdict
is the `success` key.

**bolt refuses to reuse an output directory, and writes that refusal into
`result.yaml` as `"success": false` with `kind: bolt-refused`.** So a stale
directory yields a failing verdict for a run that never happened. Give it a fresh
`--output-dir`, or read the `reasons` before believing the verdict.

**This is wrench's own jig and not the shared standard.** toolbox's
`bolt.*-std-quality.yaml` are still in the retired format, carrying `version: 1`,
`id:`, `tags:` and `result_command:`, none of which the current `jig.schema.json`
accepts. So wrench cannot adopt them until `clank/tasks/toolbox/port-the-jigs`
lands, and waiting for that meant gating nothing at all.

So the Python pack still has no ruff, no mypy and no coverage: those come with the
shared Python jig. `clank/tasks/wrench/gate/10-a-composite-jig` is the
destination, and it is now one blocker away rather than three.

**Every task exits non-zero on its own failure**, so nothing needs an adapter.
`gofmt -l` was the only tool that would have, and `test -z "$(gofmt -l .)"` gives
it an exit status instead.

**The walk honours gitignore, and this ratio is where a regression would show
first.** 2026-08-27: 4 tracked `.json` files against 387 on disk, and the run
produced **4** executions of each matching task. So `rust/target/` and
`node_modules/` are skipped by the walk rather than by the jig, and the
`excluding: [".ephemera/**", "**/node_modules/**"]` on two tasks is belt and
braces. If those counts ever diverge, the gate has started grading build output.

    git ls-files '*.json' | wc -l
    ls -d .ephemera/<run>/work/json-parses-* | wc -l

**Three of wrench's 12 tasks let a runner select files**, which is checkable here
and is the half that matters for this repository:

    grep -c 'matching:' bolt.wrench-quality.yaml      # 3

**wrench is the only jig in the estate that does, out of 116 tasks in 26 jigs.
That half is bolt's measurement and cannot be re-derived from this repository**,
which holds one jig. bolt `cd1e6ba`, its FR-3.4f, with the script at
`bolt/bin/count-selection.py`. Do not restate it here as though it were checkable
from here; if it matters, re-run bolt's script against the estate.

So when bolt's empty-selection default lands, these three are the first
things in the ecosystem it can protect, and **none of them should carry
`allow-empty`**: each matching nothing means the schemas moved or went, which is
the stale-path defect the rule exists to catch rather than a legitimate empty.

The same checks, run by hand:

    go test -count=1 ./... && gofmt -l . && go vet ./...
    PYTHONPATH=python python3 -m pytest python/tests -q
    cargo test --manifest-path rust/Cargo.toml
    python3 ~/.projects/toolbox/bin/test-traceability.py --requirements REQUIREMENTS.md .
    ./bin/test-suite-parity.py --requirements REQUIREMENTS.md \
        --suite go='*_test.go' --suite python='python/tests/*.py' \
        --suite rust='rust/tests/*.rs' .

2026-08-27: Go ok, `gofmt` and `vet` clean, 58 Python tests passed, 35 Rust tests
plus 1 compile-fail case and 2 doc tests, traceability 35 of 35 with **exit 0**,
parity 51 tests held level across all three suites.

**The traceability figure moved without wrench moving.** It read 33 of 34 earlier
the same day. toolbox's `8daa584` taught the checker that a `## Retired` section
takes rows out of the live set, so numerator and denominator both changed and the
summary is worded differently. That is the checker working, not drift here.

**The gate holds all three packs level.** `rust-test` runs the Rust suite and
`suite-parity` compares all three, both added when `clank/tasks/wrench/parity/20`
closed. Read that from the run's own artifact rather than from this line:

    grep command .ephemera/<run>/work/suite-parity-0/manifest.yaml

**The traceability checker exits non-zero when a settled row has no test, and its
printed summary looks like a pass either way.** This document quoted that summary
as a pass while the check was failing, from before 2026-08-26 until it was caught
by the jig on 2026-08-27. `docs/LESSONS/read-the-artifact-not-the-summary-line.md`.

`clank/tasks/wrench/gate/10-a-composite-jig.planning` has the design for the
shared-jig gate this one stands in for.

## Requirements stay one file, and why

The standard layout is `docs/REQUIREMENTS/<category>/<requirement>.md`, one file
per requirement. **wrench does not use it yet**, deliberately.

**The reason changed on 2026-08-27 and the blocker is now wrench's own.**
toolbox's `cc65aad` taught `test-traceability.py` to read a directory, so that
half is done. Measured: pointed at a directory holding no rows it prints
`docs declares no requirements; refusing to pass vacuously` and **exits 1**,
which is the right answer rather than a vacuous pass.

What blocks the split now is `bin/test-suite-parity.py`, wrench's own, which
still calls `read_text()` on a single path and raises `IsADirectoryError`. So
splitting today would trade one working check for one crash.
`clank/tasks/wrench/requirements/10-split-the-contract-into-files` carries it.

**There is a live hazard in keeping one file, and it is worth knowing before the
split lands.** The checkers read a `## Retired` heading as a per-file switch:
every row below it in that file is retired, and the switch dies at end of file.
wrench's `## Retired` is the **last** section, so a row appended to the end of
`REQUIREMENTS.md` is silently retired rather than added. Appending is what a
person does when adding a requirement.

Nothing is wrong today, checked 2026-08-27: 11 rows sit below the heading and all
of them are meant to. **Add a live row inside its own numbered section, never at
the end of the file.** The split removes the hazard by construction, which is a
second reason to do it. The mechanism is silo `5addaad`, and toolbox's reading of
it is that a retired section sharing a file with live rows is the one arrangement
that can retire something silently.

Nothing is silenced and nothing is mocked here, so there is no `docs/SUPPRESSIONS/`
and no `docs/MOCKS/`. Those directories are claimed when something needs them,
never created empty.

## How it fits against its siblings

**bolt is two things at once and the distinction is source against binary.** Both
halves are true, and reading only one of them misleads.

**bolt's source is Rust** and `bolt/Cargo.toml` carries
`wrench = { path = "../wrench/rust" }`, with no `go.mod` in `bolt/` at all. So an
uncommitted change under `rust/` is bolt's build, and the Rust pack is
consumer-verified from there. Nothing in that tree builds a binary yet.

**The `bolt` this gate executes is the Go one**, and it consumes the Go pack.
`~/bin/bolt` resolves to `bolt/bin/bolt`, which `go version -m` reports as
`go1.26.6`, `cmd/bolt`. It is a **deliberate bridge** kept in place while bolt is
rebuilt, recorded at `bolt/NEXT_STEPS.md`, commit `535f86f`. Nothing about the
rebuild takes it off PATH; that happens when the Rust bolt reaches parity and the
link is moved on purpose.

**The binary was swapped on 2026-08-27 at 22:08** and this gate's result is now
reproducible from source. It reports `v0.0.0-20260827201109-7604557974a5`, built
from `bolt.go` at `7604557`, where the previous one carried `+dirty` and no commit
rebuilt it. bolt `6e3112f`.

**Reproducibility was not what decided it.** The two builds disagreed about
whether a jig is valid, because the old one bundled an older copy of these
schemas: a jig whose only fault is `version: 1` passed under the old binary and
is refused under the new one, at `/version`, got number want string. So the old
build was issuing false greens, not merely unreproducible ones. **Any gate result
in this estate from before 22:00 came from the older schema.** This gate was
re-run afterwards and is unchanged at 21 executions, `success: true`.

### A consumer enforces the schema it was built with, not the one shipped here

That is the lesson in the swap and it is structural rather than a bug. bolt
**embeds** these schemas at build time, which FR-3.5 permits and bolt wants for a
static binary. So a change here is enforced by a consumer only after that consumer
rebuilds, and nothing announces the gap.

Measured 2026-08-27: `allow-empty` landed here at 21:45, bolt was rebuilt at
22:08, and the deployed bolt accepts a jig using it. It reached the consumer
because the rebuild came after, not because committing it here was enough.

    cd .ephemera/ae-probe && bolt --output-dir out ae .    # passed: 1 execution

**So do not read a schema change as immediately enforced.** Between committing a
new constraint and a consumer rebuilding, a document this repository would refuse
still passes there, and the window is invisible from both ends.

**Additive is not automatically safe here, and that was wrong in this document
until 2026-08-27.** The two regimes hurt in opposite directions. A *restrictive*
change lets an unrebuilt consumer keep accepting what this repository now refuses,
which is what produced the false greens. An *additive* change hands an unrebuilt
consumer a key its schema does not know, and **what happens then is not settled by
this contract at all**: it is the consumer's unknown-key policy, open as bolt's
question 10. Answered "fail", every additive change breaks every consumer that has
not rebuilt, turning the window into an outage. Answered "warn", the field is
silently inert and the author sees it accepted while getting none of its
behaviour, which is quieter and arguably worse.

So reshaping a schema breaks whichever bolt consumes it at its HEAD, extending one
**may or may not** depending on a policy this repository does not own, and neither
takes effect anywhere until that consumer is rebuilt.

### The three packs do not bind the schema at the same time

Measured 2026-08-27, and the divergence is **permitted rather than accidental**:

    Go        schema.go:19   //go:embed schemas/*.schema.json      build time
    Rust      build.rs       generates include_str! per schema     build time
    Python    schema.py:33   Path(__file__).parents[2] / "schemas"  run time

Checked rather than read off the source: a constraint added to
`schemas/jig.schema.json` on disk was refused by the Python pack immediately, with
no reinstall and no rebuild. The Go and Rust packs cannot see such a change until
they are rebuilt, which is what produced bolt's false greens on `version: 1`.

**FR-3.5 allows this.** A pack *may* embed, because a static binary wants it, and
what it embeds is these files rather than a copy of its own. So this is the
contract working.

**What follows is not recorded anywhere else, so it is recorded here.** At any
moment, a Python consumer and a Go consumer of the same contract may be enforcing
different versions of it. toolbox's adapters take the Python pack and see a change
at once; bolt takes the Go pack and sees it at its next build.

**Nothing detects that.** `testdata/canonical/` holds the packs to the same
canonical form and says nothing about when they read the schema.
`bin/test-suite-parity.py` compares `COVERS:` marks and says nothing about it
either. So the one divergence between the packs that neither guard covers is
temporal, and both packs conform while it exists.

**It is not, however, the failure this document opens by naming, and saying so
was an overstatement corrected on 2026-08-27.** That failure is two
implementations disagreeing about the same input at the same moment. These packs
do not: **given the same schema bytes all three agree**, which is exactly what
`testdata/canonical/` proves. What can differ is which bytes each is holding at a
given instant, and that is a property of the estate's build topology rather than
of the packs.

The distinction decides where a fix could live. **No fourth guard inside wrench
can catch it**, because every guard here compares packs on the same input by
construction. A version stamp consumers assert against could, by moving the
disagreement into the open where a run reports it. Treating it as a hole in
wrench would be accepting blame for how the estate builds, and would send the
next reader looking for a fix where none can exist.

Bounded today by there being **one** shared bolt binary in the estate, so there is
one stale schema rather than several. That holds only while `~/bin/bolt` is a
single file, and nothing states it as a requirement.

**toolbox** is the Python pack's intended consumer, through its adapters and
checkers. FACT 2026-08-26: nothing in toolbox imports `wrench` yet. Those
adapters need upgrading to the interface defined for them, and that work depends
on a solid pack in each language they are written in.

**This is circular and worth naming.** wrench's own gate needs toolbox's
checkers; toolbox's checkers need wrench's packs. The way out is that wrench's
packs do not depend on the gate to be correct, only to stay correct, so the packs
land first and the gate follows.

**silo** owns the platform decision wrench implements:
`silo/docs/DECISIONS/yaml-everywhere-validated-against-the-decoded-structure.md`.
wrench does not make that decision and does not get to differ from it.

**clank** holds this project's work at `clank/tasks/wrench/` and findings filed
against it at `clank/inbox/wrench/`. Neither is in this repository.

## The packs

| Pack | Serves | State |
|---|---|---|
| Go | `bolt.go`, the previous Go implementation | Built, at the repository root |
| Python | toolbox's adapters and checkers | Built, under `python/` |
| Rust | bolt, which is now a Rust implementation | Built, under `rust/`, suite level with the others |
| TypeScript | Consumer not yet identified | Not built |
| Ruby | Consumer not yet identified | Not built |

`docs/DECISIONS/packs-follow-demand.md` says what decides when a pack gets
written, and it is a consumer rather than a library:
`docs/DECISIONS/which-json-schema-library-each-pack-binds.md` shows every one of
these languages has a maintained JSON Schema implementation to bind.

### The Python pack is installed editable and must stay that way

The schemas are read from `schemas/` at the repository root, two levels above the
package, so a copied install leaves the pack looking for files that are not
beside it.

    uv pip install --python ~/.local/share/mise/installs/python/latest/bin/python \
        -e ~/.projects/wrench/python

FACT 2026-08-26: `python3 -c "import wrench, pathlib;
print(pathlib.Path(wrench.__file__).resolve())"` prints
`/home/ancient/.projects/wrench/python/wrench/__init__.py`, so the editable
install is live.

**That install is not reproducible from any manifest.** A machine rebuilt from
`dotfiles/bin/setup` gets every tool and no wrench. Filed at
`clank/inbox/dotfiles/declare-wrench-and-its-bootstrap-dependency/`.

### `import wrench` fails on `/usr/bin/python3`, and no longer matters

FACT 2026-08-26: that interpreter is 3.13.5 with `yaml` and no `jsonschema`, and
`schema.py` imports `jsonschema` at module level. `env python3` resolves to mise's
3.14.7, which has all three modules and imports fine, so **anything with a
`#!/usr/bin/env python3` shebang gets the working one.**

**This used to be a constraint and is not one now.** The pack was shaped around
`dotfiles/bin/setup` running on the system interpreter before mise exists. That
premise was disproven on 2026-08-26: nothing in `dotfiles/bin/` imports wrench or
reads YAML at all, its manifests are TOML read with stdlib `tomllib`, and wrench
is installed after mise. FR-7.4 is answered and retired;
`docs/DECISIONS/the-pack-is-installed-after-mise-not-before.md` has the
measurements.

So `sudo apt install python3-jsonschema` is **no longer owed**. Do not run it on
wrench's account.

Read FR-6.2a as being about which interpreter, not about whether wrench can be
imported. Read the other way, it has already misled one project.

## What holds the packs level

The shared fixture set in `testdata/canonical/`, nine cases, plus the same tables
asserted in every suite. **No pack is the oracle for another**: if they disagree,
the fixture is right.

2026-08-27: all three packs produce byte-identical canonical output for all nine
cases, each checked by its own suite. That is the acceptance test for a pack.

**All three suites cover the same rows**, since `clank/tasks/wrench/parity/20`
closed. What divergence remains is declared rather than accidental:

    FR-6.1, FR-6.2         python only. A Python pack reaching a Python
                           environment, which no other pack can discharge.
    FR-4.1 edge, negative   go and python only. Refusing a value with no
                           canonical form needs a value Rust cannot construct.

**A scope may name kinds as well as suites**, which is what FR-4.1 needs: every
pack covers it for `property`, and only two can cover its `edge` and `negative`
cases. `[A go,python:edge,negative]` says exactly that, and scoping the whole row
instead was measured to break, reporting the `property` test Rust does hold as
wrongly cited.

**FR-2.2 is the same situation with the other answer.** Its negative case is a
call naming no codec or no IO, which in Rust does not compile, so `trybuild`
asserts the compiler refuses it instead of scoping the row away. Where a compile
failure is what there is to observe, observe it.

Regenerate it rather than trusting this paragraph. `bin/test-suite-parity.py` is
the check, it names every divergence, and **it exits non-zero when it finds one**:

    ./bin/test-suite-parity.py --requirements REQUIREMENTS.md \
        --suite go='*_test.go' --suite python='python/tests/*.py' \
        --suite rust='rust/tests/*.rs' . ; echo $?

2026-08-27: 51 tests held level across go, python and rust, with 2 rows and 2
requirement/kind pairs scoped to a subset, exit 0.

**This was not bookkeeping.** It started at seven rows the Go pack held alone,
and a row exercised in one pack is a row the other can break silently. That is
measured, not hypothetical: a schema change once landed green in Go because the
only test of that schema lived in the Python suite.

`docs/PATTERNS/holding-two-packs-level.md` is what keeps it this way, and what to
follow when changing any of this. Assert the same table in every suite; a table
that differs is packs that differ. Its name predates the third pack and the
pattern is unchanged by it.

## What is not done

`clank/tasks/wrench/` is the register. In summary: the gate is wrench's own jig
rather than the shared standard, so the Python pack still has no ruff, mypy or
coverage; the Go pack is at the root rather than under `go/`; and three questions
in `NEXT_STEPS.md` are open and not blocking.

There is no git remote. FACT 2026-08-26: `git remote -v` prints nothing. That is
the expected state across this ecosystem while the history rewrite settles, and
re-adding one is not this project's call.
