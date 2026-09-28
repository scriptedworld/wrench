# A newer interpreter's syntax silently excludes the older one

`adapters/python/coverage.py`, which this repository links from toolbox and bolt runs as
a task's adapter, came back from a formatter with

    except OSError, ValueError:

where it had been `except (OSError, ValueError):`. PEP 758 makes the parentheses
optional in Python 3.14, so a formatter targeting 3.14 removes them as redundant.

Two interpreters, two answers:

    mise python3       3.14.7   accepts it
    /usr/bin/python3   3.13.5   SyntaxError: multiple exception types must be
                                parenthesized

So a file can be reformatted into something the system interpreter cannot parse, and
every check that runs under the newer one passes. toolbox's own gate did.

## Why this reaches wrench

The adapter is a symlink into toolbox, so a change there lands here with nothing in
this repository moving. FR-6.2a already records that `/usr/bin/python3` and the
interpreter an `env python3` shebang resolves to are different pythons carrying
different packages. This is the same split one layer down: not which packages are
present, but which syntax parses.

An adopter whose interpreter is the system one gets a `SyntaxError` where it expected
a coverage verdict, and the message names the adapter rather than the cause.

Filed for toolbox, which owns the formatter and the adapters, at
`clank/inbox/toolbox/a-formatter-rewrote-an-adapter-into-syntax-3-13-cannot-parse`,
with the fixture and the probe.

## What to do

When a linked file changes shape and you are about to conclude it is broken, run it
under both interpreters by name and print the version beside the verdict. Ask which
Python a construct requires, not whether it looks right.

    /usr/bin/python3 -m py_compile <file>
    python3 -m py_compile <file>

Do not read `python3 -m py_compile` exiting 0 as "this is portable". It answers for one
interpreter, the one that happens to be first on PATH.

## The other half, which cost more

`except OSError, ValueError:` reads as Python 2 to anyone who has written Python for
long enough, and that reading is now wrong. A probe here parsed the file with
`ast.parse` and reported it clean; the clean answer was correct and was disbelieved,
because the line looked obviously broken.

The probe was rewritten to print the interpreter version, the resolved path and the
offending line next to the verdict, and only then did the disagreement resolve. A
verdict with no statement of what produced it loses an argument against a strong prior,
even when the verdict is right.
