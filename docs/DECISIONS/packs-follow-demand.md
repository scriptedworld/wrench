# Packs follow demand

## The decision

A language gets a pack when something in the ecosystem needs to read or write a
structured file in it. Not before.

## Why

A pack is not free after it is written. It is a second implementation that every
schema change has to land in, a second suite that has to assert the same tables,
and a second thing that can be forgotten. `docs/LESSONS/` carries what forgetting
one costs, measured.

So the question for a new pack is not "would this language be nice to support"
but "what is blocked without it".

## What each pack serves

| Pack | Serves | State |
|---|---|---|
| Go | bolt, which reads and writes every structured file through it | Built |
| Python | toolbox's adapters and checkers | Built |
| Ruby | Named as wanted, consumer not yet identified here | Not built |
| Rust | Named as wanted, consumer not yet identified here | Not built |

CLAIM 2026-08-26: Ruby and Rust are wanted eventually, stated in session. What
they unblock is not written down yet, and this decision says that is the thing to
establish before either is built.

## wrench is upstream of the checkers

CLAIM 2026-08-26: toolbox's adapters and checkers need upgrading to the interface
defined for them, and a solid pack in each language they are written in is a
prerequisite for that work. So pack demand is not hypothetical. It is on the
critical path for the gate every project here runs, and it is chicken-and-egg
with wrench's own gate, which needs those same checkers.

`clank/tasks/wrench/` carries what follows from that.

## Retired requirement ID

This replaces FR-5.4, retired 2026-08-26. It stated a policy for choosing work
rather than a property of wrench, so no test could discharge it.
