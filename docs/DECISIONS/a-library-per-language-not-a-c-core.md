# A library per language, not a C core with bindings

Decided before the first pack was written, and recorded here rather than in
`docs/REQUIREMENTS/` because it says why the project is shaped as it is instead of
stating a property anything can test.

## The decision

Each language gets its own library implementing the contract. There is no C core
that the others bind to.

## Why

**The codecs are the easy half.** Reading and writing YAML is solved everywhere,
and canonical emission is a few hundred lines whatever the language.

**JSON Schema validation is the hard half, and C has nothing comparable.** Go has
`santhosh-tekuri/jsonschema`, Python has `jsonschema`, and both track the
specification including the 2020-12 dialect wrench declares. A C core means
implementing the specification rather than binding to one, which trades a
solved problem for an unsolved one and puts wrench in the business of being a
JSON Schema implementation.

**Cgo costs static linking and cross-compilation**, which is what bolt most wants
to keep. A bolt binary that needs a shared object beside it is a bolt that cannot
be dropped onto a machine and run.

## What holds the packs level instead of shared code

The shared fixture set in `testdata/canonical/`, plus the same tables asserted in
both suites. Agreement comes from both packs being tested against the same
declared cases, not from both calling the same code.

`docs/PATTERNS/holding-two-packs-level.md` is the shape that keeps that true.

## Retired requirement IDs

This replaces FR-5.1 and FR-5.1a, retired 2026-08-26. They stated the reasoning
above as requirements, and no test could ever have discharged them.
