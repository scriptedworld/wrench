# wrench, what is not done

Open questions and the context behind them. Sized work is in
`clank/tasks/wrench/`; this file holds what is not yet a task.

## The Zig pack is agreed, and it is a spike about Zig before it is a pack

Agreed by our user 2026-08-30, and for a reason the task did not previously
carry: **to assess Zig as what to reach for when something must be small and
fast**, in the role Go and Rust hold today. Go is not being retired. The task is
`clank/tasks/wrench/library/70-a-zig-pack.planning`, at `.planning` rather than
`.ready` because a whole pack is a fortnight and it needs splitting first.

**The libraries are settled and measured**, named by remote and commit because
the names collide badly:

    h0rv/jsonschema.zig    15577ff   validator, 10 of 10 ref forms, no deps
    cloudboss/yaml-zig     cde5c1d   YAML, official suite 402/402, 21/21 escapes
    OrlovEvgeny/serde.zig  dd8cc6f   TOML only, matches FR-4.10 and FR-4.9 exactly
    std.json                         JSON, and it answers FR-4.11 unasked

**Two rulings from our user land in the contract when the pack is built, and
not before.** Both are written up in the task with their consequences.

`-Dparity=level` against `-Dparity=native`, a build option choosing whether the
pack is held level with the other three. Level widens past int64 and is the
default; native keeps the digits Zig can hold. **This makes FR-4.10 conditional,
which is a contract change**, and the proposed amendment sits in the task rather
than in `docs/REQUIREMENTS/` because a conditional requirement with no
implementation is a row nothing discharges. It ratifies with the pack.

Support every reference form rather than only wrench's four. That sized as a
substantial upstream pull request against the validator a previous session had
named, and costs nothing against the one measured: see
`docs/LESSONS/the-first-library-named-is-not-the-field.md`.

### What the assessment found, so nobody re-runs it

FACT 2026-08-30, two tools agreeing, `evidence/` in the task holds the repro:

    small     Zig, decisively. 348KB stripped against Go's 3.5MB and Rust's
              5.9MB, and about four times lower fixed cost than either.
    fast      Rust. About three times better marginal cost per document.
    crossover about three documents per process.

**The blockers are tooling and churn, not capability.** Zig ships no coverage
tool at all, which hard rule 5 makes load-bearing here; the infobot session had
to build one from sanitizer guards, and it works only in Debug because a release
build folds the code being measured. And of thirteen Zig libraries built that
day, three do not compile on 0.16.0 and three more hide a working library behind
a broken `build.zig`: the ecosystem is split across the 0.16 boundary in both
directions.

### Three open questions, all our user's

**Splitting the task.** It is one session's work only after it is split, and the
first piece should be the spike rather than the pack.

**Whether the serde.zig defect goes upstream.** Its YAML `Value.deinit` frees
borrowed memory, with a 40-line reproducer in the task's evidence. wrench will
not hit it, because YAML moved to cloudboss and serde is kept for TOML only. So
this is a courtesy report and it is outward-facing.

**Where `ast-yaml` lives.** A tool built this session that prints a tree-sitter
parse tree as canonical wrench YAML, DOT or Mermaid.
`evidence/HOMELESS-TOOLS.md` in the task carries the trade: the Python version
travels anywhere pip does, the Rust version has no escaper because it emits
through wrench's own codec and is tied here by a path dependency for exactly
that reason. Its name is also wrong now that it emits three formats.

## Ready and unblocked

    schemas/40   a document names its own schema, cross-checked rather than
                 trusted. Both consumers agreed in their own words and toolbox
                 committed to writing the key.
    schemas/50   the unanimity check, now that the shape is decided.
    parity/40    numbers agree on range and type, mechanism first.
    prose-cleanup/20   a cold read of the sweep, which cannot be the writer.
    gate/05      the Go pack under go/.
    gate/10      a composite jig, whose premise the conversion restores.
    schemas/60   drop the retired jig task fields.


**`schemas/40` is the largest and it changes the error contract in three
packs.** A caller and a document disagreeing about what a file is fits none of
the seven kinds: it is not `validate`, because the document may be perfectly
valid against the schema it names, and it is not `schema`, which is a schema
that will not compile. An eighth kind is the likely answer and it lands in every
pack at once.

Its other open half is toolbox's question and is the good one: what does a
document that omits the key get? If the answer is silently fine, the check only
ever fires on producers who opted in, which are the ones least likely to be
wrong, and it reads as coverage while never running against anything that could
fail. Unclaimed has to be distinguishable from checked and correct. Decide it
while specifying; do not let it default.

## Blocked

Nothing.

**The cutover is done**, at `dotfiles 19df074`. `bolt` is a release build of
bolt `cf37c50` and `bolt.go` stays installed under its own name. bolt's session
checked all seven distinct jigs against an empty directory before switching, so
validation and `requires` were exercised without running anybody's suites, and
none refused.

wrench's gate was re-run afterwards rather than assumed: `success: true`, 28
executions, nothing false anywhere including both children. Falsified in the
same configuration, which is the one that gates from now on.

wrench's own half is done. It held the estate's only two `jig:` tasks across all
35 jigs; they are command tasks composing through
`adapters/common/bolt-result.py`, and both builds run the gate green at 28
executions.

## Not yet started, and each is somebody else's to settle first

**A Justfile.** Every project gets one, calling bolt as often as possible, with
a two-word interface. Our user has placed it in the standard python, go and rust
project templates rather than in toolbox, and floated a `factory` project
holding copier templates for all three. Silo owns the recipe names and is asking
rather than inventing them.

Two constraints any recipe here has to respect, both measured: it must not name
a fixed `--output-dir`, because bolt refuses a directory that already holds a
run and the Go build rewrites the earlier verdict while refusing; and it must
read `success` in `result.yaml` rather than bolt's exit status or summary line,
which hard rule 6 already requires.

The Rust build preserves the earlier verdict, so the first constraint is a
property of the build in service today rather than of bolt. It still shapes the
recipe, because a recipe outlives the cutover and the refusal remains.

**The estate-wide threshold rule.** Above the context limit the permitted set is
the prepare-clear skill, `START_HERE.md` and `NEXT_STEPS.md`, and nothing else.
It is a whitelist of two literal paths and one skill, so a rule enforcing it is
a string comparison rather than an inference about intent. Silo owns the rule
and grim the mechanism; the finding is at
`clank/inbox/silo/a-session-ran-past-90-percent-without-stopping`.

**Source comments are in the writing standard's scope**, ruled for wrench by our
user. That was an open estate question and the ruling should reach silo, since
qwark left its Go comments alone on the opposite reading.

## The Rust crate cannot be packaged, and something has to give

`cargo package` builds the tarball and then fails to verify it:

    Packaged 22 files, 149.2KiB
    Verifying wrench v0.3.0
    error: failed to run custom build command for `wrench v0.3.0`
      reading .../rust/target/package/schemas: No such file or directory

`rust/build.rs` reads `../schemas`, one level above the pack, which is the one
copy every pack reads and is deliberate. It is also outside the crate, so the
tarball does not carry it and the packaged crate cannot build.

**Two things in the repository already assume this works.** `README.md` says the
Rust pack declares its licence in `Cargo.toml` "so a consumer resolving either
through a package index sees it without reading the tree", which presumes index
distribution. And the reasoning recorded for why Rust needs no
`shipped-schemas-are-current` gate task is about staleness only: `build.rs`
regenerates every build so its copy cannot go stale. That is correct and does
not reach packaging.

Go and Python do not have this. Both carry the schemas as committed generated
source, so both are self-contained by construction. Rust is the only pack whose
schemas exist solely because of where the directory sits.

**The question is whether the crate is meant to be published at all.** bolt takes
it by path today, so nothing is broken in service. If publishing is intended,
`build.rs` needs a copy inside the pack or the generated source committed as the
other two do, and FR-3.2's one-copy rule has to say which. If it is not, the
README's package-index sentence is describing something that will not happen and
should say so.

**And `just dist` leaves the pack unbuildable until it is cleaned**, which is the
worse half. `build.rs` resolves `../schemas` from `CARGO_MANIFEST_DIR`, so during
package verification that becomes `target/package/schemas`, and the path is
cached in the build script's `rerun-if-changed`. An ordinary `cargo test` in
`rust/` then panics on a path under `target/package/` that never existed:

    thread 'main' panicked at build.rs:28:29:
    reading .../rust/target/package/schemas: No such file or directory

`rm -rf rust/target/package` restores it, and so does `just clean`. Measured
here, including the recovery, so a session that runs `dist` and then a suite is
not left guessing.

Found by `just dist` in the Rust pack, which the factory's notes predicted would
have an opinion for exactly this reason.

## The inbox

Empty. Four bolt entries were resolved: three acted on, and the fourth promoted
to `schemas/60` blocked, because dropping the retired jig task fields would make
bolt refuse the jig that runs wrench's own gate.

**toolbox holds a second copy of `jig.schema.json` and it is now out of step**,
since `allow-empty` became `optional` here. That field has already caused this
drift once. They have been told.

## Housekeeping owed

Nothing. Every `.complete` task in `clank/tasks/wrench/` names commits, and
every one of them resolves. Measured 2026-08-29 over 22 tasks: 20 carry a
`## Landed` section, and the two that do not, `prose-cleanup/10` and
`schemas/20`, name their commits in prose instead.

**Check that by heading rather than by hex.** `\b[0-9a-f]{7}\b` matches
`defaced` and several other English words, so it reports a task as documented on
the strength of its prose:

    cd ~/.projects/clank/tasks/wrench
    for d in $(find . -name '*.complete' -type d); do
        grep -qE '^## Landed' "$d"/*.md 2>/dev/null || echo "${d#./}"
    done

**Resolve against the right repository.** A `## Landed` block names one per
line, and a task that touched both names a clank commit beside the wrench one.
Checking every SHA against wrench reports the clank ones missing.

## Standing hazards

**Nothing announces which build `bolt` resolves to**, and the two differ in what
a refusal costs: the Go build rewrites the earlier `result.yaml` while refusing
a used output directory, and the Rust build preserves it. Run `bolt.go` to name
the Go build explicitly. `docs/PROJECT.md` carries what to do.

**A consumer enforces the schema it was built with.** No guard here can catch
the window, and `docs/LESSONS/a-consumer-enforces-the-schema-it-was-built-with.md`
explains why none could.

**A checker can pass while asserting nothing**, which happened three times in
one session to a check written that same day. Require a new check to be seen
failing for the reason it exists before trusting it green.

**The voicing lessons are in `docs/LESSONS/` and apply to anything written
here**, including source comments and commit messages. Read them before a prose
pass rather than after:

    a-comment-that-re-argues-a-settled-decision
    a-document-that-restates-another-becomes-the-stale-copy
    a-rewrite-pass-cuts-the-sentence-that-tells-you-to-check
