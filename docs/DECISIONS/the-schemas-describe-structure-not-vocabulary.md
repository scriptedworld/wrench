# The schemas describe structure, not vocabulary

A shipped schema constrains the **shape** of a document: which properties exist,
what types they take, what is required, how they nest. It does not enumerate the
**values** a producer may put in an open string field, and it does not carry a
list of the values in use.

Asked twice, by two sessions, about two different fields. The
answer was the same both times, so it is written here rather than re-derived a
third time.

    silo         may `metadata.statistics` enumerate the permitted metric keys
    ~/.projects  may `reasons[].kind` carry a non-normative list of kinds in use

No to both, and no to the softer form as well.

## Why not enumerate

`reasons[].kind` already says it in its own description: *"a closed list would
make a schema change the price of a new kind of failure."*

The sharper reason is the estate's build topology. **Go and Rust embed these
schemas at build time and Python reads them at run time**, measured, and
`FR-3.5` permits it. So an enumerated set makes every new kind or metric a
rebuild of every embedded consumer, with an invisible window in which a value is
legal in this repository and refused in a deployed binary. That window has
already produced false greens once, when a stale embedded copy accepted a jig
this repository refuses.

## Why not a non-normative list either

This is the tempting middle, and it is worse than it looks.

**A description is embedded with the schema.** `//go:embed schemas/*.schema.json`
takes the whole file, descriptions included, so a list of kinds in a description
goes stale in every embedded consumer exactly as an `enum` would. It inherits
the rebuild problem and buys no enforcement in exchange.

**A hand-maintained list of what exists, with nothing checking it, is a claim
whose check does not exist.** It is wrong the first time anybody adds a kind
without editing it, and nothing about the stale list looks stale. The family is
recorded at `clank/inbox/silo/a-claim-outliving-its-own-check/`; a register of
this kind is the purest instance available, because its whole content is a
snapshot of something that changes elsewhere.

The request that prompted this made the point by accident. It listed nine kinds,
six from bolt and three added that evening by the asker, and that list was
already a different list from the one written a day earlier.

**And it is not wrench's to hold.** `docs/PROJECT.md`: wrench establishes that a
file has the form its schema declares and stops; what an envelope's reasons
*say* belongs to the components that produce and consume them. wrench also
cannot see the estate. This repository holds one jig, and the estate-wide facts
about it are measured elsewhere and cited, never restated here.

## What the need actually is, and where it goes

The need is real and stating it plainly is better than the list: **a consumer
branching on `kind` has nothing to branch against.**

The answer is a **derived** register rather than a written one. Something that
walks the estate, collects the kinds actually emitted, and reports them is
checkable, cannot drift, and names its own scope. It belongs where the estate is
visible, which is not here.

Until that exists, a consumer should treat `kind` as it treats any open
vocabulary: branch on the values it knows and have a default for the rest. A
schema cannot save it from a kind invented after it was built, and neither can a
list.

## What the schema can do instead, and does

Describe structure hard enough that the open field is the only loose thing left.
For `reasons[]` that means `kind` is required, is a string, and is non-empty, so
a producer cannot omit it or send an empty one. That is what caught the defect
that prompted this: an adapter emitting `checker` with no `kind` at all was
refused with `at '/reasons/0': missing property 'kind'`.

The same shape answers the metrics question. A schema can refuse a source entry
with no `source` or `version`, refuse a targeted value that is a string where a
number belongs, and require a key to be snake_case. It cannot make two producers
mean the same thing by `maintainability_index`, and it should not pretend to.
