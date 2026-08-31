# A fixture set agrees about the values somebody thought of

## What happened

`testdata/canonical/` held nine cases and every pack passed them, so
`docs/PROJECT.md` said all three produce byte-identical canonical output for all
nine. That sentence was true and read as a general guarantee.

It was not one. The three packs had spelled floats three different ways since
the Go pack was written, and no fixture held a float that could tell:

    value        Python      Go              Rust
    1000000.0    1000000.0   1e+06           1000000.0
    1e21         1e+21       1e+21           1000000000000000000000.0
    1e-7         1e-07       1e-07           0.0000001

The only large number in the set was `"context_size": 1000000` in
`a-hand-emitted-status-file/canonical.yaml`, and it is an integer, so it never
reached the float branch at all.

Every pack round-tripped its own output, so FR-4.5 held everywhere. The property
that failed was agreement between packs, which is the one thing wrench exists to
provide.

## What it cost

It was found from outside, by a consumer, across a repository boundary. The
infobot session hit it while measuring whether it could use the Go pack's
encoder. Its board matches `[0-9.]+` against a value, so `1e+06` reads as `1`: a
count of a million displayed as one, with no error anywhere.

Nothing inside wrench was going to find it. The fixture set reported agreement,
both checkers were green, and `bin/test-suite-parity.py` compares which rows are
tested rather than what the tests assert.

And the measurement that followed was itself too small. The follow-up
measured the three YAML codecs; JSON and TOML had shipped hours later, so the
real surface was nine emitters and two packs disagreed with themselves. Go's
JSON wrote `1000000` for a float Python then read back as an integer, where its
own YAML wrote `1e+06`. Fixed at `7076801`, FR-4.8.

## The general shape

**A gap in a fixture set is indistinguishable from agreement.** Both look like a
green suite. Coverage of cases says nothing about coverage of the value space
inside them, and the value space is where two conforming implementations
diverge.

Choosing fixture content by hand selects for values people think of, which are
the values where implementations already agree, because those are the ones every
standard library handles the same way. The disagreements live at thresholds
nobody pictures: where `%g` switches to an exponent, where a decoder runs out of
integer, where a sign survives a zero.

## What to do instead

**Derive boundary cases from the type, not from imagination.** For each scalar,
take the value at each limit, one either side, and the sign and zero variants.
That enumeration is mechanical, so it can be written once and reviewed, where a
hand-picked set cannot be checked for completeness at all.

**Cover every codec with files rather than with copied constants.** As this is
written, `testdata/canonical/` feeds `input.yaml` only, and JSON and TOML
canonical form is asserted by a `canonicalJSON` constant hand-copied into three
suites. Two of the three codecs are held level by copy-paste, which is how the
JSON float divergence survived its own review.

**Exercise decode, not only encode.** Every number defect found the day after
FR-4.8 landed was a decode defect: they happen before an emitter runs, and a
fixture that is only ever an input to encoding cannot see them. Task
`parity/40` carries those.

## A sample is a fixture set with one member per class

The section above names the escape set as an edge and does not test it. That
edge was the next defect, found hours later: three packs spell a control
character three ways, and two write files they cannot read back.

Then the same mistake happened again inside the fix. Twelve code points were
sampled and the result reported as eight failures. Swept over 70, covering C0,
DEL, the whole C1 block and five Unicode specials, the answer is 61. The C1
range was invisible to the sample, and the error was sevenfold in the direction
that flattered this repository's own pack.

**A sample has no baseline, which is the deeper problem.** PyYAML alone, with no
wrench in the path, gives 6 ok, 61 unreadable, 3 changed. So the 61 is the
parser's rule that no emitter can move, and wrench's Python pack is that
baseline plus two escapes. The number that read as a score was a constant, and
only the sweep and the baseline together showed which column varied: silent
corruptions, 0, 0, 1.

**So sweep the range and measure the baseline before quoting either.** The sweep
is a loop over code points and the baseline is the same loop calling the library
directly; neither needs the pack under test.

## Publish the set, not the verdict

Both defects here were found by a consumer and this repository at once, and the
mechanism was the same both times: one side published something checkable, a
case list or an escape set, and the other checked it rather than agreeing with
it.

**Agreement between two implementations is not evidence, and neither is
agreement between two agents.** What made the exchange work is that each side
could re-run the other's measurement and get a different answer, which is what
happened: the consumer's "your escaping is strictly better than mine" survived
neither sweep.

The corollary is what to send. A verdict invites assent; a set invites a check.

### Implementations of the same version are one witness, not three

Three YAML parsers were asked whether raw U+2028 survives; all three said yes
and all three were wrong. YAML 1.1 makes it a line break and 1.2 does not, so
they agreed because they share an era rather than an argument.

A poll of implementations answers what happens here today, never what the
contract is. Where a specification exists it is the only independent witness,
and reading it took minutes where three probes took an hour and were confident.

**The tell is a question about a rule wearing a question about behaviour's
clothes.** "Does this round trip" is answerable by probing; "is this a line
break" is not.

## What does not help

Adding the value that just bit you. `floats-never-use-an-exponent` is now the
tenth fixture and it closes this instance. It does nothing about the next scalar
type, which is why the lesson is the enumeration rather than the case.
