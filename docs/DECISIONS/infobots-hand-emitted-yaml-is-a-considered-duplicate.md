# infobot's hand-emitted YAML is a considered duplicate, not a second dialect

Resolves `clank/inbox/wrench/infobot-hand-emits-a-file-wrench-owns-the-form-of/`,
filed from infobot 2026-08-26.

## The question

infobot writes `~/.local/state/infobot/<session>.status.yaml` on every render,
emitting YAML by hand, a line at a time, in nine lines of `_canonical` and
`_scalar`. Its FR-1.11d says so deliberately.

wrench owns the form of the ecosystem's structured files and ships a Python pack,
so the filer asked whether there are now two answers to "what is canonical YAML
here", and offered three resolutions. **The first one is what happened.**

## The measurement

FACT 2026-08-26. infobot's real emitted file, from the finding's
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
measurement does not disturb it: the status line runs on every Claude Code event,
19ms of its 29ms is already the interpreter, and a dependency that can fail to
resolve is a dependency that can blank the line. wrench's Python pack imports
`yaml`, `jsonschema` and `referencing` at module level, so it would add to that.

### ~~`import wrench` already fails outright on `/usr/bin/python3`~~ Corrected 2026-08-26

**That was the wrong interpreter, so it was the wrong reason.** infobot caught it
after I wrote it here.

`bin/infobot` and `bin/forget-session` both say `#!/usr/bin/env python3`, and on
this machine that resolves to mise's 3.14.7, not the system 3.13.5. Retested
2026-08-26:

    /usr/bin/python3        3.13.5   yaml=yes jsonschema=NO  referencing=NO
    env python3             3.14.7   yaml=yes jsonschema=yes referencing=yes

    env python3 -c "import wrench"   -> succeeds

So under the interpreter infobot actually runs, importing wrench would have
worked. FR-6.2a is about the bootstrap window's interpreter and remains true of
it; applying it to infobot's runtime was my error.

### The reason that survives, and it is the better one

infobot's FR-1.12: **it imports the standard library and nothing else, so it runs
under whatever `python3` resolves to** rather than under one particular
interpreter. A dependency that resolves or not depending on which interpreter wins
a PATH race is the thing infobot's FR-1.9 already calls half present, and for a
status line that fails as a blank line rather than as an error anyone sees.

That holds whether or not `jsonschema` is installed anywhere, where the old reason
depended on a package state that is itself in motion: CLAIM 2026-08-26, from
infobot, `python3-yaml` is an apt package pulled in for an abandoned manifest
experiment and may be removed.

**The conclusion did not change; the ground under it did.** A status line should
not take this dependency, for a reason that does not expire when someone runs
`apt remove`.

## What stops the two drifting apart from here

The agreement is now a declared case rather than a coincidence:

    testdata/canonical/a-hand-emitted-status-file/

`input.yaml` is the natural spelling of that structure and `canonical.yaml` is
infobot's own output, copied from the finding's evidence. Both packs enumerate
that directory, so both are held to producing infobot's exact bytes, and a change
to wrench's emitter that would diverge from infobot now fails two suites.

**This is the durable half of the answer.** Two implementations agreeing once is
a coincidence; a fixture is a contract. If infobot's emitter ever changes, that
fixture is where the disagreement surfaces.

## That fixture is half of a two-repository contract

Named by infobot as its FR-1.11n, after this measurement turned an agreement into
something with two ends and no statement of what it is.

**The form is pinned independently at both ends, and neither suite reaches into
the other's tree.** wrench holds a copy of infobot's bytes and checks itself
against it; infobot checks itself against its own. They agree because both match
the same bytes, not because one imports the other.

FACT 2026-08-26: no check here resolves an infobot path. `grep -rn infobot` in
this repository hits prose in this file and the fixture's directory name.
`/home/ancient/.projects/infobot` appears twice inside the fixture, as the value
of a `cwd` key, which is data in the case rather than a path anything opens. So a
fresh clone of wrench passes with infobot absent, which is what the rule is for: a
check needing a sibling repository present fails for the wrong reason.

**So if that fixture ever fails, the question is which end moved, and the answer
is not automatically wrench.** Ask infobot before changing the fixture, the way
you would ask bolt before reshaping a schema.

## The third option, left open

The finding also offered "wrench takes a schema for the file", so a reader has
something to validate against rather than prose in infobot's requirements. That
is not refused here, it is unclaimed: the file has one consumer today and adding
a schema is cheap whenever a second appears. infobot owns that call, since it
owns the file's contract in FR-1.11g to FR-1.11m.
