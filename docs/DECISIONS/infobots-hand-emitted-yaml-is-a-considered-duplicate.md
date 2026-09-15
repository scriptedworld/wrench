# infobot's hand-emitted YAML was a considered duplicate, and the duplicate is gone

This decision is spent. infobot's hand emitter is deleted and its Go port links
wrench's Go pack, so there is one emitter and nothing left to resolve. The
record stays because the reasoning is why the duplicate was allowed to stand for
a fortnight, and because the way it ended is the useful part.

## What it decided

infobot wrote `~/.local/state/infobot/<session>.status.yaml` on every render,
emitting YAML by hand, a line at a time, in nine lines of `_canonical` and
`_scalar`. wrench owns the form of the ecosystem's structured files and ships
packs, so the filer asked whether there were two answers here to what canonical
YAML is.

The measurement said no. infobot's real emitted bytes, fed through wrench's
Python pack, came back identical:

    value = wrench.YAML.decode(infobots_bytes)
    wrench.YAML.encode(value) == infobots_bytes     # True

So the decision was that nothing changed in either project: infobot kept
hand-emitting, wrench kept its emitter, and the two agreed. infobot's argument
against importing wrench stood on its own terms. The status line runs on every
Claude Code event, and a dependency that can fail to resolve is one that can
blank the line.

## How it ended

This document named its own expiry and then did not watch for it. Its closing
section offered infobot two honest options (re-run its probe when its emitter
changes, or land its task 14 Go port so the second emitter stops existing) and
said of the second that it "removes the duplication this document is about, so
this decision is on borrowed time in the best way."

Task 14 landed and nothing here noticed. The port links the Go pack,
`internal/state/state.go` writes through `wrench.SaveYAMLFile`, and the 133-line
hand emitter is deleted. This file went on describing a duplicate that no longer
existed until somebody read it for an unrelated review, a day later.

`docs/LESSONS/a-decision-that-names-its-own-expiry-still-needs-a-reader.md`
carries what that costs and what would have caught it.

## What is still true, and what the fixture now is

The predicted failure mode arrived exactly as written. This document warned
that `testdata/canonical/a-hand-emitted-status-file/` "pins one end only", that
wrench "holds a frozen copy and never re-derives infobot's output", and that "if
infobot drifts the fixture keeps passing and silently stops representing what it
claims to". infobot then drifted: linking the pack changed its bytes on three
escape spellings (U+2028 to `\L`, U+2029 to `\P` and U+0085 to `\N`), and the
fixture kept passing, because it holds none of those three characters.

The fixture stays, and it is no longer about infobot. It earns its place on
the merits this document already gave it: a real hand-written document with
quoted keys, an escaped quote and a backslash, a float keeping its decimal point,
and numbers staying bare. That is a good case whatever wrote it. Its directory
name is now the only thing connecting it to infobot, and it is kept for the
history, not as a claim.

What replaced the two-emitter pinning is FR-1.11o in infobot, one-way, from
the emitter to its readers: a change to the published form is announced before it
lands. infobot's FR-1.11p still describes the form as pinned at both ends, which
was true of two emitters and is not true of one; correcting it is infobot's call
and is recorded in its own NEXT_STEPS.

## The third option, still unclaimed

The finding also offered that wrench take a schema for the file, so a reader has
something to validate against instead of prose in infobot's requirements. That
happened, in the other direction and better: infobot's port carries its own
`internal/state/status.schema.json`, embedded, and compiles it through
`wrench.CompileSchema`. The file is validated on the way out by the pack that
writes it. It is not in wrench's shipped set and should not be, for the reason
`what-earns-a-place-in-the-shipped-set.md` gives in its third part: the shipped
set is the vocabulary a generic runner ecosystem shares, and a Claude Code
session is not a word in it.
