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

    REQUIREMENTS.md          the contract, one document both packs implement
    NEXT_STEPS.md            open questions and context that is not work
    schemas/                 the schemas, one copy, read by every pack
    testdata/canonical/      the shared fixture set holding the packs level

    wrench.go codec.go       the Go pack, at the repository root
    file.go schema.go
    errors.go yaml.go
    *_test.go

    python/wrench/           the Python pack
    python/tests/
    python/pyproject.toml

    docs/DECISIONS/          why the project is shaped as it is
    docs/PATTERNS/           the shape to follow when working on X
    docs/LESSONS/            what a failure here cost

**The Go pack is at the root and the Python pack is under `python/`.** That
asymmetry is known and is a problem for the gate rather than for the code:
`clank/tasks/wrench/gate/10-a-composite-jig.planning` wants the Go pack moved to
`go/` so the two are symmetric bases.

## The gate: there is not one

**FACT 2026-08-26: `ls bolt.*.yaml` returns nothing, and there is no `bin/` or
`adapters/`.** wrench is not a bolt adopter. Neither pack is gated by anything
but a person typing a command.

That is the largest single gap in this repository. The Python pack has no ruff,
no mypy, no coverage and no test task that runs unattended, and the Go pack's
green run is equally nobody's job. `docs/LESSONS/` carries what that already cost
once.

What a person runs, and what the gate will run when it exists:

    go test -count=1 ./... && gofmt -l . && go vet ./...
    PYTHONPATH=python python3 -m pytest python/tests -q
    python3 ~/.projects/toolbox/bin/test-traceability.py --requirements REQUIREMENTS.md .

FACT 2026-08-26, all three at `fc6be8a`: Go ok, `gofmt` and `vet` clean, 32
Python tests passed, traceability 29 of 34 covered with 1 open and exempt.

`clank/tasks/wrench/gate/10-a-composite-jig.planning` has the design for the
gate, and names the three things outside wrench that block it.

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

**bolt** is the Go pack's consumer and builds against this working tree:
`bolt/go.mod` carries `replace github.com/scriptedworld/wrench => ../wrench`. So
an uncommitted change here is bolt's build. Reshaping a schema breaks bolt at its
HEAD, and extending one does not.

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
| Go | bolt | Built, at the repository root |
| Python | toolbox's adapters and checkers | Built, under `python/` |
| Ruby | Consumer not yet identified | Not built |
| Rust | Consumer not yet identified | Not built |

`docs/DECISIONS/packs-follow-demand.md` says what decides when a pack gets
written.

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

### `import wrench` fails on `/usr/bin/python3`, and that is recorded not broken

FACT 2026-08-26: that interpreter has `yaml` 6.0.2 and no `jsonschema`, and
`schema.py` imports `jsonschema` at module level. It works on the interpreter on
PATH, which is what bolt invokes an adapter with. FR-6.2a states it, and
`NEXT_STEPS.md` question 1 is the open half.

Owed to a person, because a Claude shell cannot run it:

    sudo apt install python3-jsonschema

## What holds the packs level

The shared fixture set in `testdata/canonical/`, five cases, plus the same tables
asserted in both suites. **Neither pack is the oracle for the other**: if they
disagree, the fixture is right.

FACT 2026-08-26: both packs produce byte-identical canonical output for all five
cases, each checked by its own suite.

**The two suites are not the same suite.** They share the fixture set, which is
the part that matters, and diverge elsewhere. FACT 2026-08-26, from the `COVERS:`
marks:

    cited by Go and not Python    FR-1.1 FR-1.3 FR-1.4 FR-2.5 FR-2.7 FR-2.8 FR-5.2
    cited by Python and not Go    FR-6.1 FR-6.2

FR-5.5 reads as though one contract is exercised twice. It is two hand-written
suites with a shared oracle, and closing that gap is worth more than adding tests
to either alone.

`docs/PATTERNS/holding-two-packs-level.md` is what to follow when changing any of
this.

## What is not done

`clank/tasks/wrench/` is the register. In summary: wrench gates nothing, the two
suites do not cover the same rows, the Go pack is at the root rather than under
`go/`, and two questions in `NEXT_STEPS.md` are open and not blocking.

There is no git remote. FACT 2026-08-26: `git remote -v` prints nothing. That is
the expected state across this ecosystem while the history rewrite settles, and
re-adding one is not this project's call.
