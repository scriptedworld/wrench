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

**Three codecs ship, and each has a pair of wrappers**, 2026-08-28:

    load_yaml_file / save_yaml_file    load_json_file / save_json_file
    load_toml_file / save_toml_file

The wrappers supply the codec and add nothing else, so validation stays in the
core call. The codec is named rather than inferred from the suffix, because
choosing a parser by filename would make behaviour depend on what a file is
called. FR-2.7, FR-2.10, FR-4.6 and FR-4.7.

**Canonical form makes wrench the wrong writer for a file a person edits.**
Comments do not survive a load and key order is sorted away, which is correct
for an envelope and destructive for a hand-written config. The README says so
where an adopter will hit it; the read half is still worth having there.

**The TOML and YAML emitters are hand-written in all three packs, and JSON now
owns its numbers everywhere.** That split was measured rather than assumed, and
`docs/DECISIONS/a-codec-emits-by-hand-when-libraries-disagree.md` carries the
rule and the check that decides it for the next format.

JSON kept its standard library until 2026-08-28, when the same check was run
over floats and the three libraries disagreed with each other and with this
pack's own other two codecs. What each pack does about it is what its language
allows, and the bytes are what the fixture holds level: Go hands encoding/json a
marshaler for floats, Rust wraps serde_json's `PrettyFormatter` and replaces
`write_f64`, and Python emits the structure by hand because `json.dumps` formats
every float with `float.__repr__` taken as a default argument, which no
parameter reaches and no subclass overrides. Python still calls `json.dumps` for
string escaping, which is the part of the library that was right.

## Layout

    docs/REQUIREMENTS/       the contract, one file per requirement, nested by
                             category. `.retired` in a name retires that file
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

**2026-08-28: green.** `result.yaml` carries `"success": true` with no reasons,
and every one of the 23 task artifacts reads true, including both nested Python
jigs and all ten of `python-std`'s own tasks. Read them rather than the top-level
key; the loop that does is in this document's own instructions below.

Everything the shared Python standard found when the pack was wired to it in
`4ca9005` is cleared, and none of it was silenced: `lint` at `9e72e6f`,
`docstrings` at `650aa30`, `cognitive` at `69c8553`, and the rest with
`488e723`. `clank/tasks/wrench/gate/30` carries what each one was.

**Two lines are silenced, and the register is now checked.** `SUPPRESSIONS`
carries both bandit pragmas on the one test that runs a subprocess. Since
toolbox `6ac4304` the register is read by `suppressions` in `common-quality`,
which reports `2 pragma(s) across 9 source file(s)`. Before that it matched
gosec's `G\d+` and passed vacuously.

**That upgrade is the sharpest example this repository has of a symlinked
checker changing a verdict with nothing here moving.** `bin/suppression-register.py`
is a symlink into toolbox. The upgrade landed at 07:16:47 on 2026-08-28, seven
minutes after wrench's last commit, and turned the gate red on two rows that had
never been read by anything. It is the run-time-binding hazard this document
describes for schemas, arriving through a checker instead, and in the useful
direction: the gate started grading something it had been ignoring.

`bolt.wrench-quality.yaml` is wrench's own jig over the schemas, the packs and the
contract, and it now delegates the Python base to toolbox's `common-quality` and
`python-std-quality`.

## THE GATE BREAKS THE DAY `~/bin/bolt` MOVES TO THE RUST BUILD

**Nested jigs are retired.** bolt removed them at `f3304d8`, 2026-08-28: a task
never names a jig, it names `bolt` in its command like any other tool. 26
requirement rows went with it.

**wrench holds the estate's only two tasks written against the retired field**,
`python-common` and `python-std`. Measured here, running wrench's gate under
`~/.projects/bolt/target/debug/bolt`:

    bolt: task python-common carries the retired jig field;
          run the jig as a command instead, bolt <jig> <directory>

    result.yaml   "success": false, kind: bolt-refused

The gate is green today only because `~/bin/bolt` still resolves to the **Go**
build, `bolt.go/bin/bolt`. Nothing announces the switch.

**Check which binary you are running before believing a verdict**, because the
two builds disagree about whether this gate is even runnable:

    ls -la ~/bin/bolt

**DO NOT CONVERT THE TWO TASKS YET, and the reason is a trap rather than a
preference.** The adapter that reads a child run's `result.yaml` does not exist;
it is filed against toolbox as `an-adapter-that-reads-a-child-runs-result`.
Without it a task running `bolt <jig> <dir>` falls to the exit-code adapter, and
bolt exits 0 whenever it carried a run out. Measured on the Rust build:

    a run whose only task ran `false`   exit code 0, result.yaml "success": false

So a converted task would report **pass** however badly the child failed. That is
worse than the refusal, which at least stops. This is the same hazard as "read
`result.yaml`, never the exit status", arriving structurally rather than as a
habit.

**Check which binary you ran before quoting what bolt does.** Measuring against
bolt's tree on 2026-08-28 found two Rust builds giving opposite answers to the
same probe: `target/release`, built at 14:15, predated `f3304d8` and said "nested
jigs are specified and not built yet", while `target/debug` at 19:53 gave the
retired-field message above.

bolt deleted the stale one and wrote it up as
`bolt/docs/LESSONS/a-second-build-answers-for-the-tree.md`, `960edbb`. **Deleting
it is not the fix**, since `cargo build --release` re-creates it; bolt's
`docs/PROJECT.md` now says build first and use `target/debug`.

**Their reason for treating it as worse than a stale document is the part worth
carrying here.** A document is read as prose and weighed. A binary is run, and
its output is evidence — so it defeats the measure-rather-than-believe check by
supplying a measurement. Wrench's own habit of re-running a claim rather than
citing it would not have caught this; running the wrong binary IS re-running it.

**Read `result.yaml`, never the exit status.** bolt exits 0 whenever the run
completed, whatever the tools concluded, and says so in its own usage. The verdict
is the `success` key.

**Nor the summary line, which is a third thing and is wrong.** bolt's last line
of stdout labels the TOTAL execution count with the run's overall verdict, so it
reads as a count of failures and is not one. Measured 2026-08-28 on this gate:

    stdout          failed: 23 execution(s)
    result.yaml     3 reasons, and 4 artifacts reading false

23 was every execution in the run. The same run passing prints `passed: 23`.
Found by the skid session and filed at
`clank/inbox/bolt/the-summary-line-counts-every-execution-as-failed/`; the
figures above are wrench's own instance of it. Nothing here parses that line,
checked, and this note is so nothing starts.

**bolt refuses to reuse an output directory, and the Go build DESTROYS the
previous run's verdict doing it.** Measured 2026-08-29 by checksum, because the
two writes land in the same second and an mtime comparison says nothing:

    run 1   "success": true    sha 4a24d4d8fc6e
    run 2   "success": false   sha bf88e7f0978d   the refusal, overwriting it

So a stale directory does not merely yield a failing verdict for a run that never
happened: **it replaces a real one.** A caller that checks whether `result.yaml`
exists is answered `true` about the wrong run, and reading its `success` gets that
run's answer, which is worse than an absent file because absence is detectable.

**Always give a fresh `--output-dir`**, and never point one at a directory
holding a result worth keeping.

The Rust build returns before writing, deliberately, which preserves the first
result; bolt records the Go behaviour as FR-10.7's destructive shape. So this
hazard goes when the symlink moves, and until then it is live in the binary that
runs this gate.

**The shared standard is adopted for the Python base and nowhere else.** The jig
runs `bolt common-quality python/` and `bolt python-std-quality python/` as two of
its own tasks, so the Python pack does have ruff, mypy, pylint, complexipy,
vulture, interrogate, bandit and coverage. The Go and Rust packs do not: Go has no
base of its own, which is `gate/05`, and there is no shared Rust standard to join.
`clank/tasks/wrench/gate/10-a-composite-jig` is where the rest of that goes.

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

**Three of wrench's 14 tasks let a runner select files**, which is checkable here
and is the half that matters for this repository:

    grep -c '^  - name:' bolt.wrench-quality.yaml     # 14
    grep -c 'matching:' bolt.wrench-quality.yaml      # 3

Both re-measured 2026-08-28. **The denominator read 12 and had been wrong for
longer than anyone noticed**, while the numerator was right the whole time. It
went stale the ordinary way, by tasks being added and the sentence about them not
being re-run, and nothing could have caught it: the figure sat beside a command
that produces the *other* number. Printing both is what makes the sentence
checkable rather than half-checkable.

**wrench is the only jig in the estate that does, out of 116 tasks in 26 jigs.
That half is bolt's measurement and cannot be re-derived from this repository**,
which holds one jig. bolt `cd1e6ba`, its FR-3.4f, with the script at
`bolt/bin/count-selection.py`. Verified 2026-08-28 that both still resolve, and
that `cd1e6ba` resolves in `bolt` and **not** in `bolt.go`, so the citation names
one tree after the split. Do not restate the estate figure here as though it were
checkable from here; if it matters, re-run bolt's script.

So when bolt's empty-selection default lands, these three are the first
things in the ecosystem it can protect, and **none of them should carry
`allow-empty`**: each matching nothing means the schemas moved or went, which is
the stale-path defect the rule exists to catch rather than a legitimate empty.

The same checks, run by hand:

    go test -count=1 ./... && gofmt -l . && go vet ./...
    PYTHONPATH=python python3 -m pytest python/tests -q
    cargo test --manifest-path rust/Cargo.toml
    python3 ~/.projects/toolbox/bin/test-traceability.py --requirements docs/REQUIREMENTS .
    ./bin/test-suite-parity.py --requirements docs/REQUIREMENTS \
        --suite go='*_test.go' --suite python='python/tests/*.py' \
        --suite rust='rust/tests/*.rs' .

2026-08-28 at `6b2d139`: Go ok, `gofmt` and `vet` clean, 79 Python tests passed,
36 Rust tests plus 9 codec tests, 1 compile-fail case and 2 doc tests,
traceability 39 of 39 with **exit 0**, parity 60 tests held level across all
three suites.

**The requirement count drifts upward without anyone re-measuring it**, and this
document carried 35 while the contract held 38. Take it from the checker rather
than from a sentence: the number it prints is the number of rows held to
coverage, and it is the only one that cannot go stale.

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

`clank/tasks/wrench/gate/10-a-composite-jig` has the design for the shared-jig
gate this one stands in for. It was `.ready` on 2026-08-28.

**The suffix is deliberately not part of that path.** Task state is carried by
the directory's suffix, so a citation including one is a claim about state that
goes stale silently and still resolves, pointing at a task in a different state
than the sentence says. This one said `.planning` after the task became `.ready`.
Cite the stem, which is stable, and date the state separately so the two can
disagree out loud.

## The contract is one file per requirement

`docs/REQUIREMENTS/<category>/FR-<id>-<slug>.md`, nested as deep as the grouping
wants, which is the standard layout. 39 live rows and 11 retired, split from a
single `REQUIREMENTS.md` on 2026-08-28.

**Retirement is carried by the filename**, `FR-7.4-the-bootstrap-consumer.retired`,
and a retired requirement keeps the category it always sat in, so a reader
meeting an old id finds it where the series lived.

**That is what the split was for, and the hazard it removed was real.** The
checkers read a `## Retired` heading as a per-file switch: every row below it is
retired and the switch dies at end of file. wrench's heading was the **last**
section, so a row appended to the end of `REQUIREMENTS.md` was silently retired
rather than added, and appending is what a person does when adding a
requirement. No checker could catch it, because nothing distinguishes a live row
that fell under the heading from a genuine retirement. A filename has no
heading, no switch and no below-this-line. The mechanism is silo `5addaad`.

The interim `retired-rows-are-deliberate` gate task, which pinned the count of
retired rows, went with the split.

**Both checkers gave identical verdicts before and after the split**, which is
what says the contract survived the move: on 2026-08-28, traceability 35 of 35
exit 0 and parity 51 tests level across three suites, with the same 2 scoped rows
and 2 scoped pairs. Those two numbers are the split's, and both have grown since;
the current pair is below and is the one to quote.

**A `##` heading in a `.retired` file used to un-retire every row below it, and
no longer does.** `test-traceability.py` reset its retired state at every `##`
heading regardless of the filename, contradicting its own docstring. Fixed at
toolbox `31a7b6b`: a name-retired document ignores its headings entirely, which
is the reading `bin/test-suite-parity.py` already had, so the two checkers agree
and wrench's guard stays.

    git -C ~/.projects/toolbox cat-file -e 31a7b6b

Every file here still uses a single `#`, which is now a preference rather than a
workaround.

**The fixtures still carry `../REQUIREMENTS.md` as a string and that is
correct.** `testdata/canonical/` and the three suites use it as an arbitrary
value exercising the definitions, jig and manifest schemas. It never pointed at
wrench's own contract, so the split does not touch it.

**Two lines are silenced and nothing is mocked.** `SUPPRESSIONS` carries both,
with the question asked and the answer given: `B404` and `B603` on the one test
that runs a subprocess to prove the pack imports in a clean interpreter, which
is the only way to observe FR-6.1. The pragmas are line-scoped, so a second
subprocess anywhere in the suite is still reported.

**That register is checked, since toolbox `6ac4304`.** It had read `*.go` only
and matched gosec's `G\d+` rather than bandit's `B\d+`, so it passed vacuously
here; agent-support filed it and toolbox landed it. `suppressions` in
`common-quality` now reports `2 pragma(s) across 9 source file(s)`.

**A row is written in the frame the scan speaks, not this file's.**
`common-quality` runs at each pack's own base, so the checker reports
`tests/test_wrench.py` while `SUPPRESSIONS` sits one level up at the repository
root. A row is also one pragma's set of codes rather than one file's, so two
line pragmas of one code each are two rows. Both spellings caught wrench out
when the upgrade landed, at `87b49ac`.

**A shared register cannot serve two bases at once**, which wrench becomes when
`gate/05` moves the Go pack under `go/` and `gate/10` adds `go-common`. The same
document would need one path for the scan at `python/` and another for the scan
at `go/`, and either choice fails the other. Filed with a repro as
`clank/inbox/toolbox/a-shared-register-serves-two-bases`.

There is no `docs/MOCKS/`. That directory is claimed when something needs it,
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
re-run afterwards and the swap did not change its verdict. What changed it half
an hour later was `4ca9005` adopting the shared Python standard, so the verdict
above is red for that reason and not for this one.

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

**That install is not reproducible from any manifest**, still true and
re-measured 2026-08-28: nothing under `dotfiles/bin/` mentions wrench at all. A
machine rebuilt from `dotfiles/bin/setup` gets every tool and no wrench.
`dotfiles/repos.live.toml` names wrench, but that is the repository roster rather
than anything that installs it.

It was filed at `clank/inbox/dotfiles/declare-wrench-and-its-bootstrap-dependency/`,
which no longer exists because resolving an inbox entry means deleting it.
**Deleted does not mean fixed**, and from this side the three resolutions are
indistinguishable: acted on, promoted to a task, or rejected all leave the same
absence. That is why the claim above is re-measured here rather than inferred
from the entry being gone.

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

The shared fixture set in `testdata/canonical/`, ten cases, plus the same tables
asserted in every suite. **No pack is the oracle for another**: if they disagree,
the fixture is right.

2026-08-28: all three packs produce byte-identical canonical output for all ten
cases, each checked by its own suite. That is the acceptance test for a pack.

**A fixture set proves agreement only over the values it holds, and for floats it
held none that could tell.** Until 2026-08-28 the nine cases carried no float
outside the range where three different standard libraries happen to agree, so
the set reported agreement while Go wrote `1e+06` for a million, Rust wrote
`1000000.0`, and Go's JSON wrote `1000000`. Nothing was broken in any pack: each
round-tripped its own output, and the property the fixtures assert was the one
property that could not see it. `floats-never-use-an-exponent` is the tenth case
and FR-4.8 is the rule; `clank/tasks/wrench/parity/30` carries the measurement.

**Read that as the general caution rather than as a closed defect.** The set
covers what somebody thought to put in it, and a gap in it looks exactly like
agreement.
`docs/LESSONS/a-fixture-set-agrees-about-the-values-somebody-thought-of.md`
carries what it cost and what to do instead, which is to derive boundary cases
from each type rather than from imagination.

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

    ./bin/test-suite-parity.py --requirements docs/REQUIREMENTS \
        --suite go='*_test.go' --suite python='python/tests/*.py' \
        --suite rust='rust/tests/*.rs' . ; echo $?

2026-08-28: 60 tests held level across go, python and rust, with 2 rows and 2
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
delegating the Python base to the shared standard, so the Python pack has ruff,
mypy, pylint and coverage while the Go and Rust packs have no base of their own;
the Go pack is at the root rather than under `go/`; and the open questions in
`NEXT_STEPS.md` are not blocking.

There is no git remote. FACT 2026-08-26: `git remote -v` prints nothing. That is
the expected state across this ecosystem while the history rewrite settles, and
re-adding one is not this project's call.
