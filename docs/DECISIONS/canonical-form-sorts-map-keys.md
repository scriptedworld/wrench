# Canonical form emits map keys in sorted order

## The decision

A mapping is written with its keys in sorted order, in every pack.

## Why

**A YAML mapping has no order of its own**, and a Go map has none either. So
sorting is what makes two runs over the same structure produce the same bytes.
Without it, canonical form is not canonical: the same envelope written twice
differs, and a diff between two results shows movement that is not change.

**A language whose maps preserve insertion order has to sort anyway.** Python
dicts keep insertion order, so a Python pack that emitted in natural order would
produce output that depended on the order its caller happened to build the
structure in, and would disagree with Go the moment a caller built it another
way.

So this is not a Go workaround that other packs inherit. It is the rule, and
insertion order is the thing every pack has to discard.

## What catches a pack that does not

`testdata/canonical/keys-are-sorted`, run by both suites. That is what makes this
checkable rather than a convention, and it is why a new pack runs the fixture set
before it is believed.

## The scope of the sort

Keys only. A **sequence** has an order of its own, that order is data, and no
pack reorders one. Sorting a list would change what the file says rather than how
it is written.
