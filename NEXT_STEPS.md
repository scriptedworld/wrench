# wrench, what is not done

Open questions and the context behind them. Sized work is in
`clank/tasks/wrench/`; this file holds what is not yet a task.

## Ready and unblocked

    schemas/40   a document names its own schema, cross-checked rather than
                 trusted. Both consumers agreed in their own words and toolbox
                 committed to writing the key.
    schemas/50   the unanimity check, now that the shape is decided.
    parity/40    numbers agree on range and type, mechanism first.
    prose-cleanup/10   70 markdown files, plus source comments and task files.


**`schemas/40` is the largest and it changes the error contract in three
packs.** A caller and a document disagreeing about what a file is fits none of
the seven kinds: it is not `validate`, because the document may be perfectly
valid against the schema it names, and it is not `schema`, which is a schema
that will not compile. An eighth kind is the likely answer and it lands in every
pack at once.

Its other open half is toolbox's question and is the good one: what does a
document that omits the key get? If the answer is silently fine, the check only
ever fires on producers who opted in, which are the ones least likely to be
wrong, and it reads as coverage while never running against anything that could
fail. Unclaimed has to be distinguishable from checked and correct. Decide it
while specifying; do not let it default.

## Blocked

    gate/05      the Go pack under go/. The embed problem is solved; the move
                 waits on something being able to use the symmetry.
    gate/10      a composite jig. Its premise went with nested jigs.
    schemas/60   drop the retired jig task fields. Dropping them makes bolt
                 refuse the jig that runs wrench's own gate.

**The cutover has two blockers left and neither is wrench's.** The
`bolt-result` adapter does not exist and its entry is one of eighteen in
toolbox's inbox. And the Rust build has no install path, producing only
`target/debug/bolt`; that is our user's decision. The Go binary turns out to be
gitignored too, so the two are the same kind of thing and the question is where
a built binary is installed rather than which one is committed.

wrench's own half is its two `jig:` tasks, still the only ones in the estate
across all 35 jigs, and they wait on the adapter.

The naming collision is gone. The Go build is now `bolt.go` as well as `bolt`,
so the cutover is one symlink repoint and the old implementation stays
reachable by name.

## Not yet started, and each is somebody else's to settle first

**A Justfile.** Every project gets one, calling bolt as often as possible, with
a two-word interface. Our user has placed it in the standard python, go and rust
project templates rather than in toolbox, and floated a `factory` project
holding copier templates for all three. Silo owns the recipe names and is asking
rather than inventing them.

Two constraints any recipe here has to respect, both measured: it must not name
a fixed `--output-dir`, because bolt refuses a directory that already holds a
run and the Go build rewrites the earlier verdict while refusing; and it must
read `success` in `result.yaml` rather than bolt's exit status or summary line,
which hard rule 6 already requires.

The Rust build preserves the earlier verdict, so the first constraint is a
property of the build in service today rather than of bolt. It still shapes the
recipe, because a recipe outlives the cutover and the refusal remains.

**The estate-wide threshold rule.** Above the context limit the permitted set is
the prepare-clear skill, `START_HERE.md` and `NEXT_STEPS.md`, and nothing else.
It is a whitelist of two literal paths and one skill, so a rule enforcing it is
a string comparison rather than an inference about intent. Silo owns the rule
and grim the mechanism; the finding is at
`clank/inbox/silo/a-session-ran-past-90-percent-without-stopping`.

**Source comments are in the writing standard's scope**, ruled for wrench by our
user. That was an open estate question and the ruling should reach silo, since
qwark left its Go comments alone on the opposite reading.

## The inbox

Empty. Four bolt entries were resolved: three acted on, and the fourth promoted
to `schemas/60` blocked, because dropping the retired jig task fields would make
bolt refuse the jig that runs wrench's own gate.

**toolbox holds a second copy of `jig.schema.json` and it is now out of step**,
since `allow-empty` became `optional` here. That field has already caused this
drift once. They have been told.

## Housekeeping owed

**18 of the 20 `.complete` tasks in `clank/tasks/wrench/` name no commit SHA.**
A completed task is supposed to name what landed it, and reviewing one should
turn up commits that resolve. These say they are done and cannot show it.

    cd ~/.projects/clank/tasks/wrench
    for d in $(find . -name '*.complete' -type d); do
        grep -qE '\b[0-9a-f]{7}\b' "$d"/*.md 2>/dev/null || echo "${d#./}"
    done

The two completed most recently do carry them. Retrofitting the rest means
re-deriving which commits did what for each, which is real work rather than a
tidy-up, and is why it was not done on the way past.

## Standing hazards

**The gate breaks the day `bolt` moves to the Rust build**, and nothing
announces the switch. Run `bolt.go` to name the current build explicitly.
`docs/PROJECT.md` carries what to do.

**A consumer enforces the schema it was built with.** No guard here can catch
the window, and `docs/LESSONS/a-consumer-enforces-the-schema-it-was-built-with.md`
explains why none could.

**A checker can pass while asserting nothing**, which happened three times in
one session to a check written that same day. Require a new check to be seen
failing for the reason it exists before trusting it green.

**The voicing lessons are in `docs/LESSONS/` and apply to anything written
here**, including source comments and commit messages. Read them before a prose
pass rather than after:

    a-comment-that-re-argues-a-settled-decision
    a-document-that-restates-another-becomes-the-stale-copy
    a-rewrite-pass-cuts-the-sentence-that-tells-you-to-check
