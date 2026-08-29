# A check that answers a weaker question than the one it is named for

The name is the bolt session's. **In every instance the check ran, reported
success, and had not looked at the thing.**

## The collection is bolt's, and this file is not it

`~/.projects/bolt/docs/LESSONS/a-check-that-answers-a-weaker-question.md` is the
authority and grows as instances turn up. **It states its own current count and
says that a version reporting fewer is not the one being maintained.** Read it
there; a number repeated here would be a second copy of the thing that already
drifted once.

That drift is this repository's other lesson happening to this one,
`a-document-that-restates-another-becomes-the-stale-copy`, in the file least
likely to be suspected of it. The remedy that lesson gives is the one applied
here: point at the source, and let what stays be what only this repository can
say.

**Where the collection should live is open and is silo's**, at
`clank/inbox/silo/a-cross-repository-lesson-collection-lives-in-one-project/`.
It spans four repositories, which `CLAUDE.md` layers as silo's tier, and sits in
a project tree. Nothing here is blocked on the answer.

## The six this file was written from, 2026-08-28 to 2026-08-29

A dated snapshot, kept because the analysis below is measured against it and not
against whatever bolt's holds now. **Read bolt's file for the current set.**

    bolt      a summary line labelling the TOTAL execution count with the run's
              verdict, so "failed: 23" was every execution rather than 3 failures
    silo      a clear-list staleness flag computed and never printed, so a stale
              handoff and a current one produced identical output
    toolbox   a requirement id grammar of `[a-z]?`, so a row with a two-letter
              suffix is absent from the denominator rather than reported
    bolt      `cargo test` green while `bolt rust-quality .` failed, the suite
              blind to the depth the gate was exporting
    wrench    an exit code read through `| tail -3`, so the number quoted was
              `tail`'s status
    wrench    two writes inside one second compared by mtime, which said
              "unchanged" about a file that had been replaced

The last two are wrench's own and are why this file exists here at all.

## What makes them one thing

**Each check is well formed, runs, and returns a clean result.** None is broken
in a way a test would catch, because each does exactly what it says. The gap is
between what it is *named for* and what it *interrogates*.

    named for                      actually answers
    did the run fail               how many executions were there
    is this handoff stale          (nothing; the value was discarded)
    is every requirement covered   is every requirement I could PARSE covered
    do the tests pass              do the tests pass in the environment I set up
    what did the command exit      what did the last stage of the pipe exit
    did the file change            did the file change in a different second

**The dangerous property is that the weaker question is usually a subset of the
stronger one**, so the check is right whenever it matters least and silent
exactly when it matters most.

## Why measuring does not save you

This repository's habit is to re-run a claim rather than cite it, and **four of
the six above survived that habit**. Running the wrong binary is re-running.
Reading through a pipe is measuring. The check fires, and from the inside a
check that did not happen is indistinguishable from one that passed.

What caught them was a second source that disagreed:
`docs/LESSONS/vary-one-thing-or-the-measurement-cannot-say-which.md`.

## What to do

**Ask what the check would report if the thing it examines were absent.** If the
answer is the same as when it is present and correct, the check is not doing the
work its name claims.

That is one question, answerable at the desk, and it finds all six. The
two-letter requirement row is the cleanest demonstration: add it and remove it,
and `test-traceability.py` says `41 of 41, exit 0` both times.

**Then close it by comparison rather than by fixing the instance.**
`bin/test-requirement-count.py` counts the files on disk and compares them
against what the checker managed to read, which does not depend on the grammar
and so survives whatever the next unparseable id turns out to be.

**Where the thing checked is a built artefact, compare bytes and not `mtime`.**
`cargo build --release && cmp -s target/release/bolt bin/bolt` is bolt's, and
`cp` sets a fresh `mtime` whatever it copied, which is the same trap as this
file's own sixth instance reached from the other direction.

`docs/LESSONS/read-the-artifact-not-the-summary-line.md` is this lesson's first
four instances in wrench alone, written before the class had a name.
