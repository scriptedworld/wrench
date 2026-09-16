# wrench, what is not done

Open questions and the context behind them.

## Open, and each is specified enough to start

### The fixture set still compares bytes

FR-5.5 asks that any pack's output decode to the same value in every other pack,
and `testdata/canonical/` asks each pack to reproduce one golden file. All three
packs meet the stricter test. Re-basing the set on structures is what the
contract change leaves undone, and it is the mechanism that would hold a fourth
pack level without every pack writing the same bytes.

`testdata/parity-tree.json` is the 53-key tree the packs were measured against
across codecs, and nothing reads it yet.

### The Go pack has no tags, so every consumer gets a pseudo-version

`git tag` lists nothing, and Go takes its versions from tags, so
`go get github.com/scriptedworld/wrench/go@latest` resolves to a commit stamp:
infobot carries `v0.0.0-20260904181338-f34be142d905` today. The Rust and Python
packs both moved to 0.4.0 for the reference change, and the Go pack could not
move with them because it has no number to move.

Two questions, and neither is answered. Whether to tag at all: a pseudo-version
is honest about there being no release, and `an-unbumped-version-is-a-change-nobody-receives`
argues the other way, that a consumer of a surface change should be able to see
one. And at what number: `go/v0.4.0` matches the sibling packs and claims a
history of four minor versions the tags do not have, while `go/v0.1.0` is the
conventional start and puts the three packs on different numbers for the same
surface, which is the thing the shared version was for.

Tag form is `go/vX.Y.Z`, because the module lives in a subdirectory.

### A document names its own schema, cross-checked and not trusted

This is the largest of them and it changes the error contract in three packs. A
caller and a document disagreeing about what a file is fits none of the seven
kinds: it is not `validate`, because the document may be perfectly valid against
the schema it names, and it is not `schema`, which is a schema that will not
compile. An eighth kind is the likely answer and it lands in every pack at once.

Its other half is the harder question: what does a document that omits the key
get? If the answer is silently fine, the check only ever fires on producers who
opted in, which are the ones least likely to be wrong, and it reads as coverage
while never running against anything that could fail. Unclaimed has to be
distinguishable from checked and correct. Decide it while specifying; do not let
it default.

### The unanimity check

The shape is settled and the check is unwritten: the gate asks every validator
wrench binds and requires them to agree, plus at least one implementation no
pack binds. `docs/DECISIONS/the-gate-asks-every-validator-and-requires-agreement.md`
has why. Measure first whether each binding can validate against the 2020-12
meta-schema without reaching the network, because the whole shape rests on it
and none has been asked.

### Numbers agree on range and type, mechanism first

The rules are settled and the agreement mechanism is not. FR-4.10 carries the
range rule and FR-4.11 carries `-0`, both landed. Go's YAML still gives an `int`
where its JSON gives an `int64`, and that is a decode defect a fixture set
feeding YAML only cannot catch. Every divergence found so far has been on the
decode path, which is why the mechanism is the work and the rules are not.

### Smaller items

A cold read of the prose sweep, which by its own design cannot be the writer.

The voice review's leftovers. The sweep commits took most of it; checked
2026-09-15, tracked source outside Markdown still carries 6 dated comments, 3
`Measured`/`Verified` labels and about 18 comment lines in capitals, and the
Markdown carries 47 bold spans. Rewriting the commit history it also scored is
a separate decision and has not been taken.

A pre-commit hook that calls a `just` recipe, the estate standard filed in
silo's inbox as `pre-commit-runs-just-recipes-in-every-repository`. wrench
already has one installed, `.git/hooks/pre-commit.local` linked to
`bin/githooks/pre-commit`, and it runs the suppression checker directly.
Conforming means a recipe that runs the checker and a hook that calls the
recipe. How hooks are wired under the global `core.hooksPath` is silo's
question and is still open there.

A composite jig, whose premise the conversion to command tasks restores.

Dropping the retired jig task fields from the jig schema is declined. Removing
them would not make the runner refuse the jig that runs wrench's own gate: no
jig in the estate carries a `jig:` task, across all six, and
`bolt.wrench-quality.yaml` already uses the command-task-plus-adapter form and
says so in the comment above its composed tasks.

The branch stays for a reason that has not expired, and it is in the schema's own
`$comment`: bolt refuses a task carrying `jig` with kind `jig-task-retired` and a
message naming the replacement. Remove the branch and such a task fails
`'command' is a required property`, which names neither the cause nor the fix,
and the runner never reaches its own message. Jigs outside this estate are the
only place an old one can still come from, and they need that message.

## The Rust crate cannot be packaged, and something has to give

`cargo package` builds the tarball and then fails to verify it:

    Packaged 22 files, 149.2KiB
    Verifying wrench v0.3.0
    error: failed to run custom build command for `wrench v0.3.0`
      reading .../rust/target/package/schemas: No such file or directory

`rust/build.rs` reads `../schemas`, one level above the pack, which is the one
copy every pack reads and is deliberate. It is also outside the crate, so the
tarball does not carry it and the packaged crate cannot build.

Go and Python do not have this. Both carry the schemas as committed generated
source, so both are self-contained by construction. Rust is the only pack whose
schemas exist solely because of where the directory sits.

The question is whether the crate is meant to be published at all. bolt takes it
by path today, so nothing is broken in service. If publishing is intended,
`build.rs` needs a copy inside the pack or the generated source committed as the
other two do, and FR-3.2's one-copy rule has to say which.

`just dist` leaves the pack unbuildable until it is cleaned, which is the worse
half. `build.rs` resolves `../schemas` from `CARGO_MANIFEST_DIR`, so during
package verification that becomes `target/package/schemas`, and the path is
cached in the build script's `rerun-if-changed`. An ordinary `cargo test` in
`rust/` then panics on a path under `target/package/` that never existed:

    thread 'main' panicked at build.rs:28:29:
    reading .../rust/target/package/schemas: No such file or directory

`rm -rf rust/target/package` restores it, and so does `just clean`.

## Two things a consumer of the schemas should know

toolbox holds a second copy of `jig.schema.json` and it is out of step, since
`allow-empty` became `optional` here. That field has caused this drift once
before.

A consumer enforces the schema it was built with, not the one shipped here, and
nothing in this repository can detect the gap.
`docs/LESSONS/a-consumer-enforces-the-schema-it-was-built-with.md` explains why
no guard here could.

## Standing hazards

**A checker can pass while asserting nothing.** It happened three times to one
check on the day it was written. Require a new check to be seen failing for the
reason it exists before trusting it green.

The voicing lessons in `docs/LESSONS/` apply to anything written here, including
source comments and commit messages. Read them before a prose pass, not after:

    a-comment-that-re-argues-a-settled-decision
    a-document-that-restates-another-becomes-the-stale-copy
    a-rewrite-pass-cuts-the-sentence-that-tells-you-to-check
