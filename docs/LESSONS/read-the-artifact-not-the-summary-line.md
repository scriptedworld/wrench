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

## The rule already existed

`silo/docs/LESSONS/read-the-artifact-not-the-exit-status/` says this, and the
global rules carry it as hard rule 6. Knowing it did not help. **What helped was a
gate**, because a gate cannot decide the number looked fine.
