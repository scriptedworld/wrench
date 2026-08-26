# Holding the packs level

Follow this when changing a schema, or when adding or changing behaviour in one
pack. It is the whole of what stands in for shared code: nothing here is
enforced by a gate yet, so it is a checklist rather than a guarantee.

## The invariant

Every pack ships the same schemas, produces the same bytes for the same
structure, and refuses the same documents. `REQUIREMENTS.md` is one contract that
all of them implement.

## Changing a schema

**One commit, every pack.** A schema change is not a Go change or a Python
change, it is a contract change, and a commit that lands it in one pack has left
the tree broken in the others.

1. Edit the file in `schemas/`. That is the single copy; no pack keeps its own.
2. Ask which packs exercise it, and read the answer rather than assuming:

       grep -rn '<SchemaName>' *_test.go python/tests/

   A pack that prints nothing does not test that schema. Its green run will not
   report your change either way, so add the test before you rely on it.
3. Assert the same table in both suites: the accepted document, and each rejected
   document with what is wrong with it. When the tables differ, the packs differ
   and nothing will say so.
4. Run both suites, and confirm the new tests ran rather than reading the summary:

       go test -count=1 -run '<Name>' -v ./...
       PYTHONPATH=python python3 -m pytest python/tests -q -k '<name>' -v

5. `bolt` builds against this working tree through a `replace` directive, so a
   schema reshape breaks bolt at its HEAD. Extending a schema is free; changing
   the shape of something already written is not. Tell whoever holds bolt first.

## Adding a schema

Put the file in `schemas/` with an `$id`, and nothing else is needed: both packs
read the directory rather than a list of filenames. Export a named constant in
each pack for the schemas consumers reach for by name.

`docs/DECISIONS/a-shipped-schema-is-named-by-its-id.md` says why the directory is
read rather than listed, and what it cost to find out.

## Adding a pack

Write it from `REQUIREMENTS.md` and `schemas/` without reading another pack.
`docs/DECISIONS/a-pack-is-written-from-the-contract.md` says why, and is honest
that the Python pack did not manage it.

The acceptance test is `testdata/canonical/`: every case, byte-identical output,
checked by the new pack's own suite. A pack that cannot be written from the
contract alone has found a hole in the contract, and that is a finding worth more
than the pack.

## The fixture set is the oracle, and neither pack is

`testdata/canonical/` holds the declared cases. Do not re-derive the emitter
rules by reading `codec.go`: if the two ever disagree, the fixture is right and
the pack is wrong. That is what makes agreement evidence rather than coincidence.

Adding a case means adding it once and both packs picking it up, because each
suite enumerates the directory.
