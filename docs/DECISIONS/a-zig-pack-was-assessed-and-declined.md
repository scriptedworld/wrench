# A Zig pack was assessed and declined

Three packs ship, in Go, Python and Rust. A fourth in Zig was assessed and is
not being built. Nothing is blocked on it and no consumer is waiting.

## Why it was asked

Not because a Zig consumer exists. The question was whether Zig is what to reach
for when something must be small and fast, in the role Go and Rust hold. That
makes it a question about the language rather than about wrench, and wrench was
the convenient place to ask it because a pack is a known quantity of work with a
fixture set that judges it.

## What the assessment found

Zig is decisively smaller: 348KB stripped against Go's 3.5MB and Rust's 5.9MB.
Rust is faster per document by about three times, and the crossover is around
three documents per process. So the case for Zig is a binary that has to be
small and is invoked once, which is not the shape of anything here.

The blockers were tooling and churn rather than capability. Zig ships no
coverage tool at all, which matters because coverage is judged per file and
never settled by excluding one. And of thirteen Zig libraries built against
0.16.0, three do not compile and three more hide a working library behind a
broken `build.zig`, so the ecosystem is split across the 0.16 boundary in both
directions.

The libraries themselves were not the problem. A validator, a YAML codec and a
TOML codec were all found and measured, and the validator resolved every
reference form against wrench's four.

## What was kept

The survey, in `docs/LESSONS/the-first-library-named-is-not-the-field.md`, which
names each library by remote and commit with what it passed. And the
measurement, in `docs/LESSONS/a-measurement-can-be-too-small-to-hold-what-it-measures.md`,
which carries both the figures and the reason the first set of them was wrong.

Those exist so that reopening this costs a read rather than a fortnight. Ask
again when something needs a small single-shot binary, and start from the
shortlist rather than from a search sorted by stars.

## What this does not decide

`packs-follow-demand` is unchanged and still governs. A language gets a pack
when a consumer needs one, and Zig would qualify on the same terms as any other
the day something is written in it.
