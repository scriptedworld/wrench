# Adopting a library for a codec

Follow this when adding a codec to a pack, writing a new pack, or replacing an
emitter that was written by hand. A codec is a library plus the four adapters,
or the format is not supported: `packs-agree-on-structure-not-on-bytes` is why,
and `docs/SPEC.md` says what the adapters are.

Not every maintained library is acceptable, and the test is not popularity. A
library that loses a character through its own emitter cannot be adopted, and
the loss is silent, so it has to be measured before the codec is written rather
than discovered by a consumer.

## Apply the adapters first, then measure

The adapters are not decoration on top of a working emitter. **Quoting decides
whether escaping is possible at all**: a single-quoted YAML scalar has no
escapes, so a control character inside one is written raw and read back as
something else. A check run against the bare library therefore answers a
question you do not have, and it can condemn a library that is correct under the
adapters or clear one that is not.

So configure the library the way the pack will use it, and only then run the
check.

## The acceptance check

**A round trip over the control-character fixture, one code point at a time.**
Encode, decode with the same library, and compare the string that comes back
against the one that went in. A library passes only if every point survives.

    testdata/canonical/control-characters-are-escaped/

It holds eleven values: NUL, BEL, tab, newline, escape, DEL, one C1, NEL, and
the two Unicode line separators, plus a plain string for contrast. Widen it for
the probe to the whole of C0 and the whole C1 range, and add the noncharacters
and an astral character, because a reader that refuses what its own emitter
wrote fails on those rather than on the named eleven.

Write the probe in the language being measured, keep it under `.ephemera/`, and
report the code points that were lost rather than a pass or a fail. A count of
survivors says nothing about which character a consumer will hit.

This is the check that decides adoption. Anything else about a library, its
popularity, its release date, whose name is on it, is secondary to whether it
can write a document it can read.

## Then check it against the other packs

Passing alone says the library is self-consistent, not that the pack agrees with
its siblings. Encode the shared parity tree, and decode that output with every
other pack. The contract is that each one reaches the same value, not the same
bytes, so a difference in indentation or line wrapping is not a failure and a
string coming back as a number is.

## What passing does not buy

A fixture set proves agreement over the values it holds, and a gap in it looks
exactly like agreement. The set here is pure ASCII apart from the control-
character case, and no fixture is long enough to reach an emitter's line width,
so neither non-ASCII escaping nor folding is covered by running it.
`a-fixture-set-agrees-about-the-values-somebody-thought-of` carries what that
cost the last time.
