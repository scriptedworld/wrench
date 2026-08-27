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

2026-08-27: passes, 19 executions, `success: true` in `result.yaml`.
`bolt.wrench-quality.yaml` is wrench's own jig, ten tasks over the schemas, the
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

The same checks, run by hand:

    go test -count=1 ./... && gofmt -l . && go vet ./...
    PYTHONPATH=python python3 -m pytest python/tests -q
    cargo test --manifest-path rust/Cargo.toml
    python3 ~/.projects/toolbox/bin/test-traceability.py --requirements REQUIREMENTS.md .
    ./bin/test-suite-parity.py --requirements REQUIREMENTS.md \
        --suite go='*_test.go' --suite python='python/tests/*.py' .

2026-08-27: Go ok, `gofmt` and `vet` clean, 58 Python tests passed, 16 Rust tests
plus 2 doc tests, traceability 35 of 35 with **exit 0**, parity 51 tests held
level across the Go and Python suites.

**The traceability figure moved without wrench moving.** It read 33 of 34 earlier
the same day. toolbox's `8daa584` taught the checker that a `## Retired` section
takes rows out of the live set, so numerator and denominator both changed and the
summary is worded differently. That is the checker working, not drift here.

`cargo test` and `--suite rust` are absent from the jig on purpose while the Rust
suite is short of level. `clank/tasks/wrench/parity/20` adds both.

**The traceability checker exits non-zero when a settled row has no test, and its
printed summary looks like a pass either way.** This document quoted that summary
as a pass while the check was failing, from before 2026-08-26 until it was caught
by the jig on 2026-08-27. `docs/LESSONS/read-the-artifact-not-the-summary-line.md`.

`clank/tasks/wrench/gate/10-a-composite-jig.planning` has the design for the
shared-jig gate this one stands in for.

## Requirements stay one file, and why

The standard layout is `docs/REQUIREMENTS/<category>/<requirement>.md`, one file
per requirement. **wrench does not use it yet**, deliberately.

`test-traceability.py` takes a single path and calls `read_text()` on it, so
pointing `--requirements` at a directory raises `IsADirectoryError`. Splitting
`REQUIREMENTS.md` would turn the one check this repository actually runs into a
crash.

`clank/tasks/toolbox/shared-checkers/10-read-a-directory-of-requirements.ready`
is the task that unblocks it. Until it lands, `REQUIREMENTS.md` stays one
document and this paragraph is the record of why.

Nothing is silenced and nothing is mocked here, so there is no `docs/SUPPRESSIONS/`
and no `docs/MOCKS/`. Those directories are claimed when something needs them,
never created empty.

## How it fits against its siblings

**bolt is a Rust implementation and consumes the Rust pack**, by path:
`bolt/Cargo.toml` carries `wrench = { path = "../wrench/rust" }`, and there is no
`go.mod` in `bolt/` at all. So an uncommitted change under `rust/` is bolt's
build. Reshaping a schema breaks bolt at its HEAD, and extending one does not.

**The Go pack's consumer is `bolt.go`**, the previous implementation, which still
carries `replace github.com/scriptedworld/wrench => ../wrench`. Whether that tree
is kept, retired or finished is bolt's call, and this document does not know.

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
| Rust | bolt, which is now a Rust implementation | Built, under `rust/`, suite 25 tests short of level |
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

**The Go and Python suites cover the same rows. The Rust suite is 25 tests
short**, which is `clank/tasks/wrench/parity/20` and is missing coverage rather
than missing function: a consumer exercised the whole write path through the Rust
pack on 2026-08-27 and every file a run writes round-tripped.

From the `COVERS:` marks, 2026-08-26:

    cited by Go and not Python    (none)
    cited by Python and not Go    FR-6.1 FR-6.2

Those two are the Python pack's own, about a Python pack reaching a Python
environment, and the Go pack cannot discharge them. `REQUIREMENTS.md` section 6
says so, which makes that divergence a statement rather than a gap.

Regenerate it rather than trusting this paragraph. `bin/test-suite-parity.py` is
the check, it names every divergence, and **it exits non-zero when it finds one**:

    ./bin/test-suite-parity.py --requirements REQUIREMENTS.md \
        --suite go='*_test.go' --suite python='python/tests/*.py' \
        --suite rust='rust/tests/*.rs' . ; echo $?

2026-08-27: 25 divergences, all `in go, python but not in rust`, exit 1. Drop
`--suite rust` and it reports 51 held level with 2 rows scoped to a subset, exit 0.

**This was not bookkeeping.** It started at seven rows the Go pack held alone,
and a row exercised in one pack is a row the other can break silently. That is
measured, not hypothetical: a schema change once landed green in Go because the
only test of that schema lived in the Python suite.

`docs/PATTERNS/holding-two-packs-level.md` is what keeps it this way, and what to
follow when changing any of this. Assert the same table in every suite; a table
that differs is packs that differ. Its name predates the third pack and the
pattern is unchanged by it.

## What is not done

`clank/tasks/wrench/` is the register. In summary: the Rust suite is 25 tests
short of level and neither `cargo test` nor `--suite rust` is in the gate yet, the
gate is wrench's own jig rather than the shared standard, the Go pack is at the
root rather than under `go/`, and three questions in `NEXT_STEPS.md` are open and
not blocking.

There is no git remote. FACT 2026-08-26: `git remote -v` prints nothing. That is
the expected state across this ecosystem while the history rewrite settles, and
re-adding one is not this project's call.
