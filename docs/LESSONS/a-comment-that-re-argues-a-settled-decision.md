# A comment that re-argues a settled decision

## What happened

Replacing `//go:embed` with generated source, the four-line comment above it
became sixteen. The new lines explained why generation beat embedding, what the
second copy costs, what the gate task does about it, and which packs do the
same. All of that was true, and all of it belonged to a decision record.

The same thing happened twice more the same day: nine lines above a type alias
telling the whole story of how a consumer found the annotation wrong, and nine
more in a helper's docstring arguing which error kind applied.

## Why it is wrong even though every line is true

The reasoning now exists twice. Two copies drift, and a reader cannot tell which
is current. The decision record is the one that gets reviewed, so the comment is
the copy that goes stale silently.

It also crowds out what a comment is actually for. A comment earns its place by
saying what would cost time to rediscover: a silent failure, an ordering
constraint, a tool that lies, options that must not be combined. Sixteen lines
of settled reasoning buries the one line that says `//go:embed` cannot reach
above its own package, which is the fact nobody can derive by reading the code.

## What to do

Record it once in `docs/DECISIONS/`, `docs/PATTERNS/` or `docs/LESSONS/`, and
leave a pointer.

    # What a Python caller may hand the two calls. The seams stay `str`, and a
    # path is normalised once on the way in. See
    # docs/DECISIONS/each-pack-spells-the-calls-its-own-way.md.

Three lines instead of nine, and the argument lives where somebody deciding the
next case will look for it.

The three directories exist for exactly this. A comment that is really a
decision goes in DECISIONS. Reasoning attached to a shape you should follow goes
in PATTERNS. What a mistake cost goes here.

## The tell

You are writing a paragraph a reader could disagree with. A comment states; a
decision argues. If the text is making a case, it is in the wrong file.
