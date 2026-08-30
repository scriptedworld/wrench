# wrench, what is not done

Open questions and the context behind them.

## Open, and each is specified enough to start

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

**The unanimity check**, once the shape above is decided.

**Numbers agree on range and type**, mechanism first. The range rule is settled
and the agreement mechanism is not. Go's YAML gives an `int` where its JSON
gives an `int64`, and `-0` in JSON reads as `-0.0` in Rust and `0` in the other
two. All three are decode defects and none is caught by a fixture set that feeds
YAML only.

**A cold read of the prose sweep**, which by its own design cannot be the writer.

**The Go pack under `go/`**, with the other two.

**A composite jig**, whose premise the conversion to command tasks restores.

**Dropping the retired jig task fields** from the jig schema. This is blocked:
removing them would make the runner refuse the jig that runs wrench's own gate.

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
