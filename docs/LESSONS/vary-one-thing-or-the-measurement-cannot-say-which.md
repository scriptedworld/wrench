# Vary one thing, or the measurement cannot say which thing did it

## What happened

FACT 2026-08-28. bolt's summary line prints a number that reads as a count of
failures and is not one. Two sessions measured it.

skid measured three runs: two jigs, two repositories, three different failure
counts.

    common-quality (skid)     3 executions, 2 failed, said "failed: 3"
    secrets (skid)            2 executions, 1 failed, said "failed: 2"
    common-quality (wrench)  23 executions, 3 failed, said "failed: 23"

wrench measured two runs of **one** gate, same 23 executions, differing only in
whether the tools passed.

    A   stdout "failed: 23 execution(s)"   result.yaml success:false, 3 reasons
    B   stdout "passed: 23 execution(s)"   result.yaml success:true,  0 reasons

## What each could and could not show

**skid's three showed the number is the execution total.** They could not show
what the *word* in front of it was doing, because jig, repository and failure
count all moved at once. Any of them could have been the cause.

**wrench's two showed the word follows the verdict and nothing else**, because
everything else was held fixed. One gate, one repository, one execution count.

Neither set does both jobs. Three varied runs make the finding **general** — the
`secrets` run has no nested jig in it, which rules out wrench's nesting being the
cause, and wrench is the only nesting jig in the estate. One controlled pair
makes it **unrationalisable**: 23 against 3 cannot be read as an off-by-one, where
3 against 2 can.

## The rule

**A comparison that varies several things at once can show that an effect
exists and cannot say which input produced it.** Hold everything fixed but the
one variable, and the explanation set collapses to one.

It is cheap here and it is cheap generally: run B was the same command as run A
after a fix landed. The instrument was one extra invocation.

**So when a measurement surprises you, ask what else moved.** Three packs
spelling a float three ways varied pack *and* codec, and needed a baseline — the
library alone, with wrench out of the path — before the numbers meant anything.
`docs/LESSONS/a-fixture-set-agrees-about-the-values-somebody-thought-of.md`
carries that instance.

## The other half, which is not about instruments

wrench sent skid a two-part claim: the count is the total, **and** the label
follows the verdict. skid could verify the first three times and the second not
at all, and recorded the second as wrench's claim rather than as measured.

That was correct and the reason is worth having exactly. In skid's own words:

> I had no way to check the second half, and "cannot verify" is a cheaper rule
> to follow than "sounds coherent, be suspicious".

**A coherent pair is what makes an unverified half easy to absorb.** The verified
half lends its credit to the other one, and both arrive looking measured. No
amount of suspicion scales to catching that; a convention that asks *how do I
know this* rather than *does this sound right* does, because it is answerable
without judgement.

Both halves are facts now and the entry still keeps them marked apart, so a
reader who later finds the count behaves differently on the Rust bolt knows which
claim to re-run and whose it was.
