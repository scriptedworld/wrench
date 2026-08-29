# What earns a place in the shipped set

Four schemas ship. Nothing said why those four, or what a fifth would have to be,
until silo asked whether a resolved execution graph would fit beside them on
Answering meant reconstructing a criterion that had never been
written down, which is the sort of thing that should not live in one session's
head.

## The test, in two parts

**1. The file crosses a boundary between two components.** It has a producer and
a consumer, and they are different things. That is what makes its form a contract
rather than an implementation detail, and a contract is the only thing wrench
owns.

**2. A schema over it can refuse something.** Not "is well-formed", but refuses a
document somebody could plausibly write. A schema that cannot fail is
documentation wearing a checker's clothes.

Both, not either. A file crossing a boundary whose every invariant is
unexpressible gains nothing from a schema; a refusable file that never leaves one
component is that component's business.

## The four, against it

    envelope     bolt and every producer write it, every consumer reads it.
                 Refuses a failure carrying no reasons.
    jig          a person writes it, a runner reads it. Refuses the retired
                 format, which is what caught four of toolbox's jigs.
    manifest     bolt writes it before a command runs, an adapter reads it.
                 Refuses a variable with no layer, and a manifest missing one
                 of the five locations.
    definitions  a person writes it, a runner substitutes from it. Refuses a
                 nested value, which is the whole shape of the thing.

**Authored against produced is not the axis.** Two of the four are written by a
person and two by a runner, and the set does not care. A produced document needs
no new category, which is the first thing the question got wrong.

## What does not earn a place

**An internal representation.** One component writing a file it alone reads is
free to change its form whenever it likes, and a schema there converts a private
choice into a public promise for nothing.

**A document whose only real invariant is referential integrity.** JSON Schema
cannot say "this string must equal one of the `name` values elsewhere in this
document". So for a document whose defining property is that its references
resolve, the one thing worth checking is the one thing a schema cannot check, and
what is left is shape the producer cannot get wrong.

A resolved execution graph is the worked example of both. It is derived from a
jig by the runner that will execute it, its edges pointing at nodes that exist is
its whole point, and nobody writes one by hand for a schema to refuse.

## The trigger that changes the answer

**A second producer.** The moment two components emit the same kind of document,
a schema earns its place immediately, and for the reason FR-5.7 already states:
two implementations of one contract with nothing holding them level is the
failure the shipped set exists to prevent.

Watch for it rather than deciding in advance. A document with one producer today
and two next quarter earns its schema then, and adding one is additive.

**A schema is not the same as agreement.** It can require the string `success`
and cannot make two engines mean the same thing by it. Where two implementations
must agree on *behaviour* rather than on form, the thing to share is the code
that decides, or a fixture set that holds both to the same answers. That is what
`testdata/canonical/` does for the packs here, and it is why the packs are level
where a schema alone would not have made them so.
