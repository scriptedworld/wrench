# Holding the packs level

Follow this when changing a schema, or when adding or changing behaviour in one
pack. It is the whole of what stands in for shared code: nothing here is
enforced by a gate yet, so it is a checklist rather than a guarantee.

## The invariant

Every pack ships the same schemas, refuses the same documents, and writes output
every other pack decodes to the same value. `docs/REQUIREMENTS/` is one contract
that all of them implement.

**Not the same bytes.** That was the invariant until
`packs-agree-on-structure-not-on-bytes`, and it is what forced an emitter to be
written by hand in each pack. Two packs indenting a list differently is now
noise rather than a defect; two packs disagreeing about whether a key is a
string is still the failure this file exists to catch.

## The check that enforces it

    ./bin/test-suite-parity.py --requirements docs/REQUIREMENTS \
        --suite go='go/*_test.go' --suite python='python/tests/*.py' \
        --suite rust='rust/tests/*.rs' .

**Run this before committing anything that touches a test.** It fails when a
`COVERS:` mark exists in one suite and not another, and it compares the
requirement **and the kind**, so a row where one pack asserts the positive path
and another the negative one is a divergence rather than agreement.

That distinction is not theoretical. Comparing ids alone reported wrench level
while three tests existed in Go and not in Python, and one of those turned up a
real behavioural difference between the packs.

**A row legitimately held by one pack declares itself** with a scope marker in
its own requirement file under `docs/REQUIREMENTS/`, such as `[python]`. The
checker reads those files, so the exempt list lives in one place. **Never add a scope marker to silence a failure**:
it is for a row a pack cannot discharge, and a row merely untested in one pack is
the finding the check exists to produce.

Adding a pack means adding a `--suite` for it, and the Ruby pack is the standing
example of what happens otherwise: it is not named in the command, so nothing
compares it to anything, and adding it reports 55 divergences.

## Changing a schema

**One commit, every pack.** A schema change is not a Go change or a Python
change, it is a contract change, and a commit that lands it in one pack has left
the tree broken in the others.

1. Edit the file in `schemas/`. That is the single copy; no pack keeps its own.
2. Ask which packs exercise it, and read the answer rather than assuming:

       grep -rn '<SchemaName>' go/*_test.go python/tests/ rust/tests/ ruby/test/

   A pack that prints nothing does not test that schema. Its green run will not
   report your change either way, so add the test before you rely on it.
3. Assert the same table in every suite: the accepted document, and each rejected
   document with what is wrong with it. When the tables differ, the packs differ
   and nothing will say so.
4. Run the suites, and confirm the new tests ran rather than reading the summary:

       (cd go && go test -count=1 -run '<Name>' -v ./...)
       PYTHONPATH=python python3 -m pytest python/tests -q -k '<name>' -v
       cargo test --manifest-path rust/Cargo.toml <name>
       (cd ruby && ruby -Ilib -Itest test/test_wrench.rb -n '/<name>/')

5. `bolt` builds against this working tree through a `replace` directive, so a
   schema reshape breaks bolt at its HEAD. Extending a schema is free; changing
   the shape of something already written is not. Tell whoever holds bolt first.

### A compiled consumer carries the schema from its own build time

The Go pack embeds the schemas with `go:embed`, so **a binary holds whatever
`schemas/` said when it was compiled**, not what the working tree says now.

That makes one verification route quietly wrong. `go build` and `go test` in a
consumer are a real check of this tree, because both recompile. **Running a
prebuilt binary is a check of whenever it was last built**, and it will report
your change as absent or the old shape as still valid.

This cost bolt ten minutes twice in one day. A binary built
before `cdef684` reported `needs-repository-root` as accepted on a jig task,
which looked like wrench's claim was wrong. It was a stale binary.

So when asking a consumer to verify a schema change, **say "rebuild first"**, and
when verifying one yourself, prefer `go test` over anything already compiled.

## Adding a schema

Put the file in `schemas/` with an `$id`, and nothing else is needed: each pack
reads the directory rather than a list of filenames. Export a named constant in
each pack for the schemas consumers reach for by name. The Ruby pack has no such
set yet, so nothing there picks a new schema up.

`docs/DECISIONS/a-shipped-schema-is-named-by-its-id.md` says why the directory is
read rather than listed, and what it cost to find out.

## Adding a pack

Write it from `docs/REQUIREMENTS/` and `schemas/` without reading another pack.
`docs/DECISIONS/a-pack-is-written-from-the-contract.md` says why, and is honest
that the Python pack did not manage it.

The acceptance test is `testdata/canonical/`: every case, decoded and re-emitted,
checked by the new pack's own suite. The three older packs compare their output
against the golden file byte for byte, which is stricter than the contract now
asks and is why re-basing that set on structures is open work.

Take the library before the emitter: `adopting-a-library-for-a-codec` is the
procedure and the check a library has to survive first.

A pack that cannot be written from the contract alone has found a hole in the
contract, and that is a finding worth more than the pack.

## The fixture set is the oracle, and no pack is

`testdata/canonical/` holds the declared cases. Do not re-derive the emitter
rules by reading `go/yaml.go`: if the two ever disagree, the fixture is right and
the pack is wrong. That is what makes agreement evidence rather than coincidence.

Adding a case means adding it once and each pack picking it up, because every
suite that reads the set enumerates the directory. The Ruby pack does not read
it, so a case added today reaches three packs and not four.
