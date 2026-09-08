# The hand-written emitter was the thing that was wrong

Three packs emitted byte-identical TOML for a document none of them could read
back. A sub-table inside an array-of-tables entry was written with a
root-relative header, so `{"a": [{"b": {"c": 1}}]}` decoded as
`{"a": [{}], "b": {"c": 1}}`, and FR-2.4 promises a saved file survives a load.
FR-2.7 carries the defect, the three source lines and the round-trip runs.

The emitters existed to control exactly that hazard. Each codec's own docstring
named it: TOML binds a bare key to the most recent header. Every maintained
library tested writes the qualified header and round trips.

## Why nothing saw it

**Agreement between implementations written from one description is not
independent evidence.** The three packs were written from the same contract, and
the contract said what the bytes had to look like, so they made the same
inference and produced the same wrong document. A cross-pack byte comparison
then reported agreement, which is what it was built to do.

The fixture set could not have caught it either: it held no nested table inside
an array of tables, and a gap in a fixture set looks exactly like agreement.

So two mechanisms both reported a defect as a pass, and neither was broken.
A single pack round-tripping its own output would have found it in one run.

## What replaced the rule

`a-codec-emits-by-hand-when-libraries-disagree.superseded` said to write the
emitter when two libraries disagree. The divergences it measured were real and
were properties rather than formats: ordering, float spelling, quoting style,
null spelling, each reachable by an adapter over a library that already gets
escaping right.

A codec is now a library plus the four adapters,
`packs-agree-on-structure-not-on-bytes`, and a library is accepted only after it
survives a round trip over the control-character fixture,
`docs/PATTERNS/adopting-a-library-for-a-codec.md`. Two hand-written YAML
emitters are still in the tree, in the Python and Rust packs.

## What to take from it

A comparison between two things built from one description tests the building,
not the description. Where the answer has to be right rather than consistent,
put the check somewhere that does not share the assumption: a round trip through
the pack's own reader, or a library that was written by somebody who never read
this contract.
