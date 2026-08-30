# A summary line that reads like a pass is not a pass

## What happened

On 2026-08-27 `bolt wrench-quality .` ran for the first time and reported
`traceability` failing. The same command had been run by hand many times that day
and every time it was reported as passing.

    python3 ~/.projects/toolbox/bin/test-traceability.py \
        --requirements REQUIREMENTS.md .

    33 of 34 requirements covered; 0 open and exempt      <- printed
    exit 1                                                <- never looked at

**`REQUIREMENTS.md` is the path as it was on 2026-08-27 and is left standing.**
The contract split into `docs/REQUIREMENTS/` on 2026-08-28. This is a record of
what was run and what it printed, so repointing the path would make the record
claim something that never happened; a live citation gets repointed, a record of
a past observation gets dated.

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

On 2026-08-27, handing the Rust pack to bolt, I warned that it refused a
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

The rule to read the artifact and never the exit status already existed, and the
house rules carry it. Knowing it did not help. **What helped was a
gate**, because a gate cannot decide the number looked fine.

## And once more, one layer down, in the evidence

`a-silent-build-failure-prints-the-number-you-wanted.md` records the third
instance: a `repro.sh` whose build silently produced no binary, so it timed a
program that did not exist and printed 0ms, which reads as a better result.

## The fourth instance is this file being ignored by the person who wrote it

2026-08-27, hours after the paragraph above about controls landed at `97d1f83`.

Asked whether a filename could mark a requirement retired, I probed it with a
file named `FR-9.1-a-thing.retired.md` that also carried a `## Retired` heading
inside. It was reported retired and I recorded that the **name** had done it.

**The name had done nothing.** The heading had done all of it, which toolbox
measured and sent back. My probe had two candidate causes and no control, so it
could only return whichever one I had brought to it.

The general form, and it is worth more than the incident:

**An experiment that cannot discriminate between two explanations returns the one
you expected.** Not the true one. Not a random one. Yours.

Re-run with the control, three files and no heading in any of them, the answer
was visible rather than inferred: `.retired` excluded, `.retired.md` excluded,
`.md` live.

**What makes this the useful instance is that the principle was already here.**
The paragraph above praises bolt for running controls and says plainly that
running only the failing case would have proved nothing. I wrote it in the
morning and failed to apply it in the afternoon, in the same repository, on a
question I cared about.

So the thing that fails is not knowing the rule. **What fails is that a
confirming result ends the investigation**, and a control is the only thing that
makes a confirming result mean anything. Ask of any probe, before believing it:
*what else would have produced this exact output?* If the answer is "something I
would be embarrassed to have missed", the probe is not finished.

## The status you read may not be the status you want

Three ways the exit status stops being the answer, in rising order of how hard
they are to see:

    cmd | tail -2 || echo FAILED     the status is tail's, and tail succeeded
    gofmt -l x && echo NOT-CLEAN     gofmt exits 0 whatever it finds, so the
                                     status was never the answer at all
    local got; [ $? = 0 ]            `local` is a command and clobbers $?, so
                                     the comparison compares nothing

The first two happened here, the second twice in one session, once while
checking whether a generated file was formatted. The third is the dotfiles
session's, found when its falsification harness reported five tests passing
under every mutation of the world they were testing.

`dotfiles/docs/LESSONS/a-status-read-one-line-late-is-not-that-command-s-status.md`
has all three. The one worth carrying here: a check that cannot fail reports
success identically to one that passed, so **run the falsification pass, and
then distrust the falsification pass.**
