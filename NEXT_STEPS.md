# wrench, what is not done

Open questions and the context behind them.

## Open, and each is specified enough to start

**The Ruby pack is built and nothing holds it to anything.** Four gaps, and the
first two are the ones that make the rest reachable:

- **Its suite reads a file no clone has.** `ruby/test/test_wrench.rb` loads
  `.ephemera/parity-tree.json`, and `.ephemera/` is gitignored, so `git archive
  HEAD` carries the suite and not the tree it needs. The shared parity tree
  belongs beside the other fixtures if every pack is to be measured against it.
- **No task runs it.** `PACKS` in the `Justfile` is `go python rust`, and
  `bolt.wrench-quality.yaml` has no Ruby task, so `just test` and the gate both
  pass without compiling a line of it.
- **The parity check reports 55 divergences** when `--suite
  ruby='ruby/test/*.rb'` is added: 16 `COVERS:` marks against the 67 the other
  three hold level. Those are tests to write, not scope markers to add.
- **It exposes no `Schemas`.** FR-5.7 says every pack exposes the same set, and
  this one carries none: a caller compiles what it hands over. Go and Python
  reach the set through a generated file and Rust through `build.rs`, so the
  question is which of the two shapes Ruby takes.

**The fixture set still compares bytes.** FR-5.5 now asks that any pack's output
decode to the same value in every other pack, and `testdata/canonical/` asks
each pack to reproduce one golden file. Three packs meet the stricter test and
the fourth is not in it. Re-basing the set on structures is what the contract
change leaves undone, and it is the mechanism that would hold four packs level
rather than three.

**The Go pack has no tags, so every consumer gets a pseudo-version.** `git tag`
lists nothing, and Go takes its versions from tags, so
`go get github.com/scriptedworld/wrench/go@latest` resolves to a commit stamp:
infobot carries `v0.0.0-20260904181338-f34be142d905` today. The Rust and Python
packs both moved to 0.4.0 on 2026-09-04 for the reference change, and the Go pack
could not move with them because it has no number to move.

Two questions and neither is answered. **Whether to tag at all**: a pseudo-version
is honest about there being no release, and `an-unbumped-version-is-a-change-nobody-receives`
argues the other way, that a consumer of a surface change should be able to see
one. **And at what number**: `go/v0.4.0` matches the sibling packs and claims a
history of four minor versions the tags do not have, while `go/v0.1.0` is the
conventional start and puts the three packs on different numbers for the same
surface, which is the thing the shared version was for.

Tag form is `go/vX.Y.Z`, because the module lives in a subdirectory.

**The Python pack writes two characters it then refuses to read.** Encoding
`{"v": <char>}` through each pack and decoding its own output:

    character              Go         Python     Rust       Ruby
    U+0085, U+FEFF         escaped    escaped    escaped    escaped
    U+200B, U+00E9         raw        raw        raw        raw
    U+FFFE, U+FFFF         escaped    RAW        raw        escaped
    U+1FFFE                escaped    raw        raw        escaped
    U+1F600 (an emoji)     escaped    raw        raw        escaped

Every cell round trips within its own pack except the two in capitals, where
`YAML.decode(YAML.encode(v))` raises `ParseError`. That is FR-4.2 failing
outright, and it is the whole of the defect. Rust emits the same bytes and reads
them back, yaml-rust2 being the more permissive reader, so no comparison between
packs would find it either.

**The pack's own emitter is what does it.** It writes the character as its raw
three bytes inside the quotes, where an escape is what the reader accepts, so
the encode side and the decode side of one pack disagree about the same
document. Handing emission to a library that escapes it closes this, which is
where `packs-agree-on-structure-not-on-bytes` was already pointing.

**The escaping divergence in the rest of the table is no longer a defect.**
FR-5.5 holds the packs to structure rather than to bytes, and an escaped emoji
and a raw one decode to the same character. What it costs is diff noise when two
packs rewrite one file, which is the cost
`packs-agree-on-structure-not-on-bytes` accepted.

**Nothing detected the round-trip fault, and the reason is structural.** Every
one of the twelve fixtures in `testdata/canonical/` is pure ASCII, and a fixture
set cannot disagree about a character it does not contain. The fix is a fixture
per case, and it is worth writing before the emitters move, not after.

**Fixing it changes the bytes the Python pack writes, and one consumer pins
them.** infobot's FR-1.11p asserts the exact bytes of wrench's output against
the pack that produces them, and its FR-1.11o requires a change to that form to
be announced before it lands. Packs no longer having to match each other does
not release a pack from the reader it already has, so this needs a version bump
here and a word to infobot first.

**A document names its own schema, cross-checked rather than trusted.** This is
the largest of them and it changes the error contract in three packs. A caller
and a document disagreeing about what a file is fits none of the seven kinds: it
is not `validate`, because the document may be perfectly valid against the
schema it names, and it is not `schema`, which is a schema that will not compile.
An eighth kind is the likely answer and it lands in every pack at once.

Its other half is the harder question: what does a document that omits the key
get? If the answer is silently fine, the check only ever fires on producers who
opted in, which are the ones least likely to be wrong, and it reads as coverage
while never running against anything that could fail. Unclaimed has to be
distinguishable from checked and correct. Decide it while specifying; do not let
it default.

**The unanimity check.** The shape is settled and the check is unwritten: the
gate asks every validator wrench binds and requires them to agree, plus at
least one implementation no pack binds.
`docs/DECISIONS/the-gate-asks-every-validator-and-requires-agreement.md` has
why. Measure first whether each binding can validate against the 2020-12
meta-schema without reaching the network, because the whole shape rests on it
and none has been asked.

**Numbers agree on range and type**, mechanism first. The rules are settled and
the agreement mechanism is not. FR-4.10 carries the range rule and FR-4.11
carries `-0`, both landed. Go's YAML still gives an `int` where its JSON gives
an `int64`, and that is a decode defect a fixture set feeding YAML only cannot
catch. Every divergence found so far has been on the decode path, which is why
the mechanism is the work rather than the rules.

**A cold read of the prose sweep**, which by its own design cannot be the writer.

**A composite jig**, whose premise the conversion to command tasks restores.

**Dropping the retired jig task fields** from the jig schema. **Declined, and
the reason recorded here was the wrong one.** It said the removal would make the
runner refuse the jig that runs wrench's own gate. It would not: no jig in the
estate carries a `jig:` task, `bolt.wrench-quality.yaml` included, which already
uses the command-task-plus-adapter form and says so at its line 158. Measured
2026-09-04 across all six jigs.

The branch stays for a reason that has not expired, and it is in the schema's own
`$comment`: bolt refuses a task carrying `jig` with kind `jig-task-retired` and a
message naming the replacement. Remove the branch and such a task fails
`'command' is a required property`, which names neither the cause nor the fix,
and the runner never reaches its own message. That is worth keeping for jigs
outside this estate, which is the only place an old one can still come from.

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

A consumer enforces the schema it was built with rather than the one shipped
here, and nothing in this repository can detect the gap.
`docs/LESSONS/a-consumer-enforces-the-schema-it-was-built-with.md` explains why
no guard here could.

## Standing hazards

**A checker can pass while asserting nothing**, which happened three times in
one session to a check written that same day. Require a new check to be seen
failing for the reason it exists before trusting it green.

**The voicing lessons in `docs/LESSONS/` apply to anything written here**,
including source comments and commit messages. Read them before a prose pass
rather than after:

    a-comment-that-re-argues-a-settled-decision
    a-document-that-restates-another-becomes-the-stale-copy
    a-rewrite-pass-cuts-the-sentence-that-tells-you-to-check
