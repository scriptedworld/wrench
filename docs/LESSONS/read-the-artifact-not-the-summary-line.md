# A summary line that reads like a pass is not a pass

## What happened

FACT 2026-08-27. `bolt wrench-quality .` ran for the first time and reported
`traceability` failing. The same command had been run by hand many times that day
and every time it was reported as passing.

    python3 ~/.projects/toolbox/bin/test-traceability.py \
        --requirements REQUIREMENTS.md .

    33 of 34 requirements covered; 0 open and exempt      <- printed
    exit 1                                                <- never looked at

**It had been exiting 1 at every commit that day**, measured afterwards across
`4677988`, `0ecab66`, `b069377`, `23338c0` and `68d583b`. The printed line reads
like a score, the score looked good, and the exit status was never checked.

## Why the summary is misleading, and it is not the checker's fault

The checker prints what it found and exits non-zero when a **settled** requirement
has no test. Those are two different statements, and only one is on screen:

    33 of 34 requirements covered      how much is covered
    exit 1                             one settled row is not, which is fatal

"33 of 34" is not a failure to a reader. It is a failure to the checker, because
the project's rule is that every settled row has a test, and 34 is not 33.

## What it cost

Nothing broke, but the report was wrong for a day and it was wrong in the
direction that matters: a check was being cited as evidence while failing. Every
"traceability 32 of 33, 0 open" said this session was a misreading.

**It was found by the gate, not by looking harder.** Wiring `bolt wrench-quality`
took a check that a person had been eyeballing and gave it an exit status nobody
could round off.

## What to do instead

**Read the exit status, and where there is an artifact, read the artifact.**

    python3 .../test-traceability.py --requirements REQUIREMENTS.md . ; echo $?

For bolt: **`bolt` exits 0 whenever the run completed**, whatever the tools
concluded. It says so in its own usage. The verdict is `success` in
`result.yaml`, and the failures are its `reasons`.

    grep '^"success"' .bolt-*/result.yaml

**Do not read bolt's stdout summary as a count of failures.** `failed: 18
execution(s)` means the run failed and there were 18 executions, not that 18
failed. Misread once here, in the same hour as the lesson above, in the opposite
direction.

## The same shape, a day later, about code rather than a check

FACT 2026-08-27. Handing the Rust pack to bolt, I warned that it refused a
non-string mapping key at the **parse** step where Go and Python refused during
**normalisation**, and asked bolt to reconcile the difference because its FR-6.11
matches on that word. I put the same warning into the follow-on task.

There was no difference. All three packs say `parsing`, because **`normalise` runs
inside the codec's decode in every one of them**, so a normalisation failure *is*
a parse failure. Normalisation has never been a separate step here.

**It was a claim about wrench's own code, and checking it was one command.** It
cost a consumer a probe to disprove, and it would have cost whoever picked up the
task an afternoon chasing a ghost.

The habit that fails here is not laziness about someone else's system. It is
assuming the shape of your own, because that is the thing you feel no need to
measure.

**bolt's method is the part worth copying.** It did not only run the failing case,
which would have proved nothing since everything-refuses looks identical. It ran
controls: a schema violation reports `validate` in all three, an unclosed flow
sequence reports `parse`. That is what made the answer mean something.

## The rule already existed

`silo/docs/LESSONS/read-the-artifact-not-the-exit-status/` says this, and the
global rules carry it as hard rule 6. Knowing it did not help. **What helped was a
gate**, because a gate cannot decide the number looked fine.
