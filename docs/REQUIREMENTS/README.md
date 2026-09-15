# wrench, Requirements

One file per requirement, `<category>/FR-<id>-<slug>.md`. Both checkers read the
tree, so a category may nest as deep as the grouping wants.

Derived from four sources and nothing else: this repository's `README.md`; the
rows in bolt's requirements that state the contract rather than bolt's use of
it; the platform decision that every structured file is YAML validated as JSON
Schema over the decoded structure; and a finding that the Python pack has to run
before pip exists. What that last one established lives in
`docs/DECISIONS/the-pack-is-installed-after-mise-not-before.md`, and its premise
was later disproven there.

Those rows have left bolt, which now states only its own use of the contract.
The move landed as bolt 3d40517.

Requirements are stated as observable properties. Each says what must be true of
wrench or of a call, not how anything is built.

A status marker says where a row comes from. `[A]` traces to a direct statement
in one of the four sources, `[D]` is derived from one, and `[A/D]` is both. `[?]`
is open, recorded so it is not lost and carrying no test yet.

A lowercase scope marker such as `[python]` names the packs expected to
discharge that row. **A row carrying none is expected in every pack.** Only
three rows carry one, all under `reaching-the-library/`.

`bin/test-suite-parity.py` reads these markers as the authority on which
divergences are intended, so a row exempt here is exempt in the check, and
nowhere else holds a second copy of that list. Adding a scope marker to silence
a failure is the one wrong use of it. The marker is for a row a pack cannot
discharge; a row that is merely untested in one pack is the finding.

## Retirement is a filename

    <category>/FR-7.4-the-bootstrap-consumer.retired

A retired requirement keeps its category, so a reader meeting `FR-7.4` finds it
where the FR-7 series always lived. **Its ID is never reused**, and the file is
what makes that checkable: the row inside it keeps the id registered as retired,
so declaring it again is caught instead of silently rewriting what every
existing reference meant.

A `## Retired` heading cannot do this safely. A heading is a per-file switch:
every row below it is retired and the switch dies at end of file. When the
contract was a single `REQUIREMENTS.md` with that heading as its *last* section,
a row appended to the end of the file was silently retired, not added, and
appending is what a person does when adding a requirement. No checker could
catch it, because nothing distinguishes a live row that fell under the heading
from a genuine retirement. A filename has no heading, no switch and no
below-this-line, so the hazard is gone by construction, and no guard pinning the
count of retired rows is needed.

The filename wins over any heading inside the file, so a `## Superseded by` in a
`.retired` document is safe. `test-traceability.py` behaves this way from
toolbox `31a7b6b`, matching `bin/test-suite-parity.py`. Before that it reset its
retired state at every `##` heading regardless of the filename, un-retiring
every row below it, against its own docstring.

Every file here uses a single `#` heading, which is the house shape.

## Every settled row carries a test

    python3 ../toolbox/bin/test-traceability.py \
        --requirements docs/REQUIREMENTS .

Read the exit status, not the summary. The checker prints a count and exits
non-zero when a settled row has no test, and the printed line reads like a pass
either way: this contract once sat failing for over a day while that line was
quoted as a pass. The rows that caused it were design notes and a platform note.
A row like that is retired to `docs/DECISIONS/` or struck once its purpose has
gone, and never excluded.
