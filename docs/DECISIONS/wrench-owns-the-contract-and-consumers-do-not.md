# wrench owns the contract, and every component reading through it is a consumer

## The decision

The form of the ecosystem's structured files is settled here. bolt, toolbox,
infobot and anything else that reads or writes one is a **consumer** of that
contract, not a co-author of it.

**No consumer's convenience settles what the contract is.** That is why the
contract is specified before a pack is written, and why the schemas are one copy
rather than one per language.

## Why it is not just tidiness

Without it, the contract becomes whatever the loudest consumer needed most
recently. Each component grows its own reader, its own emitter and its own idea
of what a valid envelope is, and they drift while all of them believe they
conform. That drift is silent: nothing fails until two components that were never
tested together have to agree.

## What it looks like in practice, measured

Two commits changed wrench's shipped schemas and were written by
the session working in bolt, landing Go-only and leaving the Python pack broken on
`main`. That is precisely the failure this decision names: a consumer changing the
contract to suit itself, with the change reaching only the pack that consumer
happened to use.

`docs/LESSONS/a-schema-change-lands-green-in-the-pack-that-does-not-test-it.md`
has the measurement.

**The repair was not a rule, it was a route.** bolt now sends the *shape* it needs
and wrench lands it in every pack with tests in one commit. That worked the same
day: `needs-repository-root` arrived as a described field, and an hour later bolt
sent a **correction**, because its first wording described a containment escape it
had since measured on its own build. Landing the second wording rather than the
first is the whole value of the arrangement. A consumer editing the schema
directly would have shipped the first.

**It cuts both ways, and that is the point.** bolt's rows are the source for what
a jig and a manifest must carry; wrench does not invent those shapes. Owning the
contract means being the place it is written down and held consistent, not being
the place it is decided alone.

## What a consumer is owed in return

- **Told before a reshape.** Extending a schema is free; changing the shape of
  something already written breaks a consumer at its HEAD. bolt builds against
  wrench's working tree through a `replace` directive, so this is immediate.
- **Landed in every pack at once**, so no consumer is the one that discovers the
  divergence.
- **A route in.** Send the shape and the reasoning; it gets tests in both packs.

`docs/PATTERNS/holding-two-packs-level.md` is that route written down.

## Retired requirement ID

This replaces FR-1.3. It stated who decides rather than a
property of wrench, so no test could discharge it. The Go test that cited it was
really testing FR-2.3, that the signature compels a schema and not the right one,
and now cites that alone.
