# wrench, Requirements

One file per requirement, `<category>/FR-<id>-<slug>.md`. Both checkers read the
tree, so a category may nest as deep as the grouping wants.

Derived from four sources and nothing else: `README.md`, the rows in
`bolt/REQUIREMENTS.md` that state the contract rather than bolt's use of it,
`silo/docs/DECISIONS/yaml-everywhere-validated-against-the-decoded-structure.md`,
and `clank/inbox/wrench/python-library-runs-before-pip-exists/`, an inbox entry
that was resolved and therefore deleted. **The path is kept because it names
where a source came from, not where to find it now**; what it established lives
in `docs/DECISIONS/the-pack-is-installed-after-mise-not-before.md`, and its
premise was later disproven there. The entry is gone, as a
resolved one should be.

Those rows have left bolt, which now states only its own use of the contract.
The move landed as bolt 3d40517.

Requirements are stated as observable properties. Each says what must be true of
wrench or of a call, not how anything is built.

**Status markers.** `[A]` traces to a direct statement in one of the four
sources. `[D]` is derived from one. `[A/D]` is both. `[?]` is open, recorded so
it is not lost and carrying no test yet.

**Scope markers.** A lowercase marker such as `[python]` names the packs expected
to discharge that row, and **a row carrying none is expected in every pack**.
Only three rows carry one, all under `reaching-the-library/`.

That is not documentation. `bin/test-suite-parity.py` reads these markers as the
authority on which divergences are intended, so a row exempt here is exempt in
the check, and nowhere else holds a second copy of that list. Adding a scope
marker to silence a failure is the one wrong use of it: the marker is for a row a
pack **cannot** discharge, where a row merely untested in one pack is the finding.

## Retirement is a filename, and that is the point

    <category>/FR-7.4-the-bootstrap-consumer.retired

A retired requirement keeps its category, so a reader meeting `FR-7.4` finds it
where the FR-7 series always lived. **Its ID is never reused**, and the file is
what makes that checkable: the row inside it keeps the id registered as retired,
so declaring it again is caught rather than silently rewriting what every
existing reference meant.

**This replaced a `## Retired` heading and the reason is worth keeping.** A
heading is a per-file switch: every row below it is retired and the switch dies
at end of file. wrench's heading was the *last* section of a single
`REQUIREMENTS.md`, so a row appended to the end of that file was silently
retired rather than added, and appending is what a person does when adding a
requirement. No checker could catch it, because nothing distinguishes a live row
that fell under the heading from a genuine retirement. A filename has no
heading, no switch and no below-this-line, so the hazard is gone by construction.

The interim guard that pinned the count of retired rows went with the split.

**The filename wins over any heading inside the file**, so a `## Superseded by`
in a `.retired` document is safe. That was not always true:
`test-traceability.py` reset its retired state at every `##` heading regardless
of the filename, un-retiring every row below it, which contradicted its own
docstring. Fixed at toolbox `31a7b6b`, matching what `bin/test-suite-parity.py`
already did.

Every file here uses a single `#` anyway. It was a workaround while that was
open and is now just the house shape.

## Every settled row carries a test

    python3 ~/.projects/toolbox/bin/test-traceability.py \
        --requirements docs/REQUIREMENTS .

**Read the exit status, not the summary.** That checker prints a count and exits
non-zero when a settled row has no test, and this contract stood in that state
for over a day while the printed line was being quoted as a pass. The rows that caused it were design notes and a platform note; each
was retired to `docs/DECISIONS/` or struck once its purpose had gone, never
excluded.
