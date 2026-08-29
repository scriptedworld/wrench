# A document that restates another becomes the stale copy

## What happened

`docs/PROJECT.md` reached 653 lines. Most of it was a second copy of something
else: the shape of the library, which `docs/SPEC.md` specifies; how requirement
retirement works, which `docs/REQUIREMENTS/README.md` explains; the schema
binding analysis, which is a lesson; and the bolt binary swap, which is git
history.

Rewritten to hold only what the file is for, it came out at 196 lines with
nothing lost.

Two of its sections had gone false. It required an editable install of the
Python pack and explained at length why, after the pack stopped needing one. A
reader following the file's own instruction would have installed the wrong way
and been told it was mandatory.

## Why the copy is the one that rots

The original gets changed because it is the authority. The copy gets changed
only if somebody remembers it exists. `PROJECT.md` was the file a session is
told to read before deciding how to do anything here, so its stale half had the
widest reach of any document in the repository.

The length is what hid it. In 653 lines a false paragraph reads as one more
paragraph.

## What to do

Point at the source instead of summarising it. A path costs one line and cannot
disagree with what it points at.

Ask what each document is for and let it hold only that. Here:

    docs/SPEC.md          how the pieces fit
    docs/REQUIREMENTS/    what must be true
    docs/DECISIONS/       why it is shaped this way
    docs/PATTERNS/        what to follow when changing it
    docs/LESSONS/         what a mistake cost
    docs/PROJECT.md       what it is, how it is gated, what is not done
    NEXT_STEPS.md         open questions that are not yet work

**Where a figure is the only claim, print the command instead.** `PROJECT.md`
already told the reader to regenerate the parity numbers rather than trust the
paragraph, while carrying thirty-one dated figures of its own that it did not
apply the same rule to.

## The tell

A section you could delete and lose nothing, because the reader would go to the
authority anyway. That section is already the stale copy; it just has not
drifted yet.
