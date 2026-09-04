# A decision that names its own expiry still needs a reader

A document can state the condition under which it stops being true and still go
on being believed for as long as nobody happens to open it. Naming the condition
feels like handling it. It is not: it moves the work from the writer to a reader
who has not been told to come back.

## What happened

`docs/DECISIONS/infobots-hand-emitted-yaml-is-a-considered-duplicate.md` closed
with this, in its own words:

> The two honest options are infobot's: re-run its probe when its emitter
> changes, or land its task 14 Go port so the second emitter stops existing. The
> second removes the duplication this document is about, so **this decision is on
> borrowed time in the best way.**

Task 14 landed on 2026-09-03. infobot deleted its 133-line hand emitter and now
writes through `wrench.SaveYAMLFile`. The document went on describing a duplicate
that did not exist until somebody read it on 2026-09-04 for an unrelated review.

That is the clean case. It was not the only one.

## It was nine, in one review of six repositories

Every one has the same shape: a reason was recorded, the reason's premise
changed, and the record stayed.

- **The decision above.** Named its expiry, was not watched.
- **infobot's FR-1.11d and FR-1.11n**, both retired rows, both asserting as
  present fact that "the port kept the hand-emitter and wrench declined the link
  on 2026-08-28". FR-1.11n's own closing line is *"retiring a row on a future
  state is the mistake here"* — and the future state then arrived, which a
  retired row cannot say.
- **infobot's FR-1.11p**, live, requiring the form be "pinned independently at
  both ends" and a change to be "a two-repository change". There is one emitter.
  infobot's own NEXT_STEPS had already written the replacement wording and
  nobody applied it.
- **wrench's NEXT_STEPS** calling the retired jig fields "blocked" because
  removal would make the runner refuse wrench's own jig. No jig in the estate
  carries a `jig:` task, and `bolt.wrench-quality.yaml` says so in its own
  comment.
- **bolt's `.gitignore`**, naming the adopted links one at a time "because that
  glob would swallow `bolt.rust-quality.yaml`, which is this project's own gate
  and IS tracked". bolt carries no jig. The same comment cited
  `bin/count-selection.py`, deleted earlier.
- **infobot's and qwark's `.gitignore`**, both objecting to a glob — correctly,
  to `bolt.*.yaml`, which does swallow their definitions file. Neither had
  revisited the narrower `bolt.*-quality.yaml` that skid used all along and that
  cannot match a `*.definitions.yaml`. The reason was about a different glob than
  the one that works.
- **bolt's runbook**, showing a `link-toolbox` transcript of six files including
  an adapter that left the set, and never mentioning the `rust` set, so a fresh
  clone followed to the letter cannot run one of its two gate runs.
- **toolbox's `docs/PROJECT.md`**, describing the Go jig as having "no coverage"
  and citing the decision that removed it — a decision whose own text says the
  removal lasted one day.
- **The coverage plan in `HANDOFF.md`**, which said lcov's branch records were
  already in the file wrench's consumers produce. cargo-llvm-cov writes `BRF:0`
  and no `BRDA` at all without a flag that needs nightly.

The last one was written the day before it was acted on, by someone who had the
whole context. Freshness is not the protection.

## Why naming the condition is not enough

`traceability` gates the direction from a requirement to a test: state a
requirement, and something fails until a test cites it. Nothing gates the
direction from a decision to its premise. A decision is prose, its premise is
usually a fact about another file or another repository, and prose has no
failing state.

So the expiry condition ends up costing more than it looks like it saves. It
reads as diligence — the writer thought about what would falsify this — while
creating an obligation with no owner and no trigger. The next reader arrives for
some other reason entirely, months later, and the document has been quietly wrong
the whole time to everyone who did not arrive.

## What would have caught these

Most of them are mechanical. Of the nine, five name a file, a requirement id, or
a jig field that a checker could resolve and find gone: the deleted adapter in
the runbook's transcript, the deleted `count-selection.py`, `bolt.rust-quality.yaml`,
the `jig:` field no jig carries, the retired FR ids asserted as current. A
checker in the family of `bin/test-traceability.py` could fail on those the same
way it fails on a test citing a requirement that does not exist.

The other four cannot be evaluated by a machine — "wrench declined the link",
"the port kept the hand-emitter" are claims about what another project chose. For
those the value is not automation but enumeration: a decision that declares a
condition should be findable as a list, so the review is a finite set somebody
can be asked to walk rather than a re-read of sixty documents.

`toolbox/docs/DECISIONS/traceability-is-a-gate-not-a-report.md` already settled
that a report gets ignored where a gate does not, which is the argument for
making the checkable subset fail rather than print. What it does not settle is
the cost: a field convention across every decision document in six repositories,
and a gate that fails the first time it runs. That is a decision, and it is
unmade.

## The cheap half, which is not

Write the expiry as a condition somebody can check without reading the
surrounding argument, and put it where a reader will be. "This decision is on
borrowed time" is a feeling. "Void when infobot's task 14 lands; grep
`_canonical` in infobot to tell" is a check. Neither is a gate, but the second
can be run by whoever next touches either repository, and the first cannot be run
at all.
