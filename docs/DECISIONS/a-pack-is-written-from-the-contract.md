# A pack is written from the contract, not by reading another pack

## The decision

Each language pack is written from `REQUIREMENTS.md` and the schemas. Reading an
existing pack to find out what to build is the thing this rule exists to prevent.

## Why

Otherwise the first implementation's accidents become the specification. A pack
written by reading the Go one inherits every choice Go made for Go's reasons,
and the contract silently becomes "whatever the Go pack does". That is the
provenance failure this whole ecosystem exists to avoid: a document that
describes an implementation is not a specification, it is a transcript.

The contract is settled first and stated independently of any implementation, so
a second pack agreeing with the first is evidence the contract is complete rather
than evidence one was copied.

## The Python pack did not meet this, and the guarantee is weaker than it reads

CLAIM 2026-08-26: the Python pack was written by the session that had just
written the Go pack, with the Go source in context. Independence cannot be
claimed for it. `clank/tasks/wrench/library/20-the-python-pack.complete/TASK.md`
records this at the time it happened.

**What actually holds the two packs level is the shared fixture set**, and that
does hold: FACT 2026-08-26, both packs produce byte-identical canonical output
for all five cases in `testdata/canonical/`, each checked by its own suite.

So the guarantee in force is "two implementations agree on a declared set of
cases", not "two implementations were derived independently". Those are different
strengths and only the first has been demonstrated.

**A Ruby or Rust pack is where this decision can still be kept.** Write it from
`REQUIREMENTS.md` and `schemas/`, run it against `testdata/canonical/`, and do
not open `wrench.go` or `codec.py` while doing it. If the contract turns out to
be insufficient to write a pack from, that is the finding, and it is worth more
than a third pack that agrees because it was copied.

## Retired requirement ID

This replaces FR-5.3, retired 2026-08-26. It stated a rule about how work is
done, which no test can discharge, and stating it as a requirement made the gate
report a permanent uncovered row.
