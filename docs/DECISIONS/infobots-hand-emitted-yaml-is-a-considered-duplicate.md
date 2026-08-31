# infobot's hand-emitted YAML is a considered duplicate, not a second dialect

Resolves a question raised by infobot, a sibling project that hand-emits a file
whose form wrench owns. This document is the resolution.

## The question

infobot writes `~/.local/state/infobot/<session>.status.yaml` on every render,
emitting YAML by hand, a line at a time, in nine lines of `_canonical` and
`_scalar`. Its FR-1.11d said so deliberately.

wrench owns the form of the ecosystem's structured files and ships a Python
pack, so the filer asked whether there are now two answers to what canonical
YAML is here, and offered three resolutions. The first one is what happened.

## The measurement

infobot's real emitted file, from the finding's
`evidence/sample.status.yaml.txt`, fed through wrench's Python pack:

    value = wrench.YAML.decode(infobots_bytes)
    wrench.YAML.encode(value) == infobots_bytes     # True

**Byte identical.** Keys quoted and sorted, one to a line, strings quoted,
numbers bare, the float keeping its decimal point, and the embedded quotes and
backslash in `"Opus 5 \"1M\" \\ context"` escaped the same way.

## The decision

**Nothing changes in either project.** infobot keeps hand-emitting, wrench keeps
its emitter, and the two agree.

infobot's argument against importing wrench stands on its own terms and this
measurement does not disturb it: the status line runs on every Claude Code
event, 19ms of its 29ms is already the interpreter, and a dependency that can
fail to resolve is a dependency that can blank the line. wrench's Python pack
imports `yaml`, `jsonschema` and `referencing` at module level, so it would add
to that.

**The reason is FR-1.12 and not the interpreter.** infobot imports the standard
library and nothing else, so it runs under whatever `python3` resolves to rather
than under one particular interpreter. A dependency that resolves or not
depending on which interpreter wins a PATH race is what infobot's FR-1.9 calls
half present, and for a status line that fails as a blank line rather than as an
error anyone sees.

That reason does not expire. An earlier version of this file argued instead that
`import wrench` fails outright on `/usr/bin/python3`, which was the wrong
interpreter: `bin/infobot` and `bin/forget-session` both say
`#!/usr/bin/env python3`, which resolves to mise's 3.14.7 here.

    /usr/bin/python3        3.13.5   yaml=yes jsonschema=NO  referencing=NO
    env python3             3.14.7   yaml=yes jsonschema=yes referencing=yes

    env python3 -c "import wrench"   -> succeeds

FR-6.2a is about the bootstrap window's interpreter and remains true of it.

## What stops the two drifting apart, and what no longer does

The agreement is a declared case rather than a coincidence:

    testdata/canonical/a-hand-emitted-status-file/

`input.yaml` is the natural spelling of that structure and `canonical.yaml` is
infobot's own output, copied from the finding's evidence. Every pack enumerates
that directory, so all of them are held to producing infobot's exact bytes, and
a change to wrench's emitter that would diverge from infobot fails three suites.

**It pins one end only, and the failure mode is inverted from what it looks
like.** infobot retired FR-1.11n along with FR-1.11d, correctly on its own
terms: its task 14 said both rows go if wrench's Go pack emits the same bytes,
and it does. Verified from both ends, the Go pack reproducing the fixture byte
for byte against a golden with exactly one commit in its history, so the
comparison is not the pack being compared with itself, and infobot re-running
`_canonical()` and still producing those 256 bytes.

What FR-1.11n bought was the other end: infobot pinned too, and a change there
being a two-repository change. Without it, **the fixture cannot fail because
infobot moved.** wrench holds a frozen copy and never re-derives infobot's
output, so if infobot drifts the fixture keeps passing and silently stops
representing what it claims to.

**The fixture stays and stops being described as a contract.** It earns its place
on its own merits: a real hand-written document exercising quoted keys, escaped
quotes and a backslash, a float keeping its decimal point, and numbers staying
bare. What it is not is evidence about what infobot currently emits.

**Do not repair this by reaching into infobot.** A check needing a sibling
repository present fails for the wrong reason. No check here resolves an infobot
path: `grep -rn infobot` hits prose in this file and the fixture's directory
name, and `/home/you/project` appears twice inside the fixture as
the value of a `cwd` key, which is data in the case rather than a path anything
opens. A fresh clone of wrench passes with infobot absent.

The two honest options are infobot's: re-run its probe when its emitter changes,
or land its task 14 Go port so the second emitter stops existing. The second
removes the duplication this document is about, so this decision is on borrowed
time in the best way.

**Ask infobot before changing that fixture, as a courtesy rather than a rule.**
Those bytes came from somewhere and infobot is who would know whether new ones
are also acceptable. Neither side is held to it now.

## The third option, left open

The finding also offered that wrench take a schema for the file, so a reader has
something to validate against rather than prose in infobot's requirements. That
is not refused here, it is unclaimed: the file has one consumer today and adding
a schema is cheap whenever a second appears. infobot owns that call, since it
owns the file's contract in FR-1.11g to FR-1.11m.
