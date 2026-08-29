# A breaking change is only safe while every consumer has somebody

## The rule

wrench may break its API when every consumer of the affected pack has an agent
or a person who can respond. Where one does not, the change is additive and the
old spelling stays until that consumer is retired.

## Why, and it is not a general caution

A version bump is the only channel a shared pack has that cannot be ignored. A
pinned dependency that will not resolve stops a build, where a stale copy runs
on silently. That is a good property and it is the argument for breaking
cleanly.

It cuts both ways. The same bump reaches a tree that has somebody and strands a
tree that does not.

`bolt.go` is the estate's counterexample. It consumes the Go pack, it gets no
agent by our user's ruling, and it is what `~/bin/bolt` resolves to, so it gates
every project here. It also still needs a rebuild to pick up schema changes
already committed, because a consumer enforces the schema it was built with. A
pack it cannot compile against takes that last rebuild away, and nobody is
coming to fix the call sites.

So the question is not how disruptive the change is. It is whether somebody is
on the other end.

## What this looked like in practice

Adding `schemas.JIG` beside `JIG_SCHEMA` cost nothing, because the two are the
same object and cannot drift. Removing `JIG_SCHEMA` would have cost bolt 43 call
sites and bolt.go its ability to be rebuilt at all.

The bolt session migrated anyway and their reason is worth recording against
this one: a guard proving two spellings agree is a guard against a situation
worth not being in, and one spelling needs no guard. Both are right. wrench
keeps both spellings because it cannot make that choice for bolt.go; a consumer
with an agent should migrate and stop paying for the second name.

## Counting the consumers, which is where this goes wrong

**Count the test package, not only the source.** Tests here live in an external
package by convention, so a suite exercises the observable surface more heavily
than the implementation does. Measured on bolt: 12 use sites in `src/` and 31 in
`tests/skeleton.rs`. An estimate from `src/` alone was a quarter of the real
number and was reported as a total.

    grep -rc '<the symbol>' src/ tests/

A count from a directory you chose is not a count. Name the directories or count
the repository.

## What to do when a consumer has nobody

State it in the change rather than working around it silently. The additive form
is usually available: a new name beside the old, an optional field beside a
required one, a widened type. Where it is not, the change waits for the consumer
to be retired, and the wait is recorded where somebody will meet it.
