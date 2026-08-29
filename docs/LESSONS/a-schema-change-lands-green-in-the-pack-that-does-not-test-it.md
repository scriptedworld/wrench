# A schema change lands green in the pack that does not test it

## What happened

Two commits changed the shipped schemas and touched Go only.

    bd62361  a schema for definitions, shared by the jig that carries them
    9b3700f  a manifest variable says which layer supplied it

`go test ./...` was green after both. The session read that, and stopped.

At that point the Python pack was broken three ways:

1. `test_all_three_shipped_schemas_load_from_the_one_copy` failed. 9b3700f made
   a manifest variable `{value, from}`, and that test asserted the old shape.
2. `DEFINITIONS_SCHEMA` did not exist. bd62361 shipped a fourth schema and Go's
   `DefinitionsSchema` and left `python/wrench/schema.py` naming three files.
3. `JIG_SCHEMA.validate` on a jig with a `definitions` block raised
   `Unresolvable`. bd62361 introduced a `$ref` between two shipped schemas; Go
   registers every schema by `$id` before compiling and Python did not.

## Why green meant nothing

**Go had no test of the manifest schema at all.**

    grep -n ManifestSchema *_test.go     # printed nothing

So the schema 9b3700f changed was exercised by exactly one test in the whole
repository, and that test was in the other pack. `go test` ran, passed, and had
not read the thing that changed.

This is the general rule biting in a specific place: an exit code says whether a
program ran, never whether what it checked was good. The one command that would
have caught it was the `grep` above, and it costs nothing.

## What it cost

Two commits sat on `main` with the tree red in a pack nobody ran. It was found by
the next session running `pytest` during `/grok`, not by a gate, because
**wrench gates nothing**: `ls bolt.*.yaml` returns nothing, so the Python pack has
no test task anything but a person runs.

Cheap this time. The same failure with a consumer downstream is a producer
writing files a consumer will refuse, discovered by the consumer.

## What to do instead

**Changing a shipped schema is a change to every pack, so land it in every pack
in one commit.** `docs/PATTERNS/holding-two-packs-level.md` is the checklist.

**Before believing a green run, confirm what it read.** For a schema change:

    grep -rn '<SchemaName>' *_test.go python/tests/    # who exercises it?

If that prints nothing for a pack, that pack did not test your change, and its
green is silence rather than agreement.

**A schema no pack validates against is a shape the gate cannot hold anything
to.** Both packs now assert the manifest table. The absence of a test was the
defect that let the other three in.
