# Packs agree on structure, not on bytes

Every pack emits through its language's own library. What the packs are held to
is that any pack's output decodes to the same structure in every other pack.
They are not held to writing the same bytes.

This retires the requirement that produced every hand-written emitter in this
repository.

## Why byte-identity cannot be kept

Byte-identity and library-only emission are incompatible, and not merely
expensive together. That was measured across all four languages on one 53-key
tree carrying control characters, the separators, unicode from four scripts,
multiline strings, the int64 boundaries and floats that want an exponent.

The block sequence is what settles it.

    library                  block sequence indentation
    libyaml, used by Rust    indentless, hard-coded, emitter.rs:732
    yaml.v3, used by Go      indented, and `SetIndent` is the only knob
    ruamel, used by Python   either
    Psych, used by Ruby      indentless

No canonical form exists that all four libraries can emit. Whichever
indentation is chosen, either Go or Rust cannot produce it, and neither has a
usable alternative: Rust's runners-up write control characters raw, and Go's
`goccy` reads its own CR back as LF.

So the real choice was between byte-identity and library emitters, and
byte-identity is the one that has to go because the hand-written emitters are
where the defects live.

## What replaces it

Semantic round-trip parity. Every pack must decode every other pack's output to
the same structure. That is checkable, it is what consumers actually depend on,
and it is what the fixture set becomes: structures that must survive every pack,
in place of bytes every pack must reproduce.

Measured before adopting it, and it already holds:

    python  4/4 files decode to the same structure
    ruby    4/4 files decode to the same structure

Four differently-shaped YAML files, from four independent emitters, agreeing in
both packs.

## The four adapters stay, and they are the real contract

A library is taken with adapters, never bare. These four are what preserve
meaning, which is the half that matters once bytes are no longer promised:

    sort the keys                two runs over one structure must agree
    quote every string and key   `no`, `1.20`, `null` and `10` stay what they
                                 were. An unquoted key is the sharp one: to a
                                 YAML 1.1 reader `10:` is an integer key
    positional floats            FR-4.8. `1e+20` read by `[0-9.]+` yields 1,
                                 which is a defect already found in the wild
    null written as the word     an empty value and a missing one should not
                                 look the same to a reader

Go and Rust each needed two further settings, and no code: no line folding, and
unicode passed through.

Several libraries already agree with wrench unprompted. libyaml's escape table
matches byte for byte including `\0 \a \b \t \n \v \f \r \e \N \L \P`, uppercase
`\x7F` and `﻿`. serde_json and Go's `encoding/json` need only the float
adapter. Those parts of the hand-written emitters were reimplementing correct
library behaviour.

## Two packs were already doing this

`go/yaml.go`'s encode side writes no text at all: it builds nodes and hands the
document to the library. `rust/src/json_codec.rs` is serde_json plus the float
adapter. Neither ever had a hand-written emitter, and both met the contract.

That is the strongest argument here. A sibling pack satisfied the requirement
without the thing the requirement was said to force.

## What it costs

A file written by one pack and rewritten by another differs in whitespace, so a
cross-pack rewrite shows diff noise. That is the whole cost.

It is narrow because a file is normally written by one producer and read by
many, and it is already being paid: toolbox's adapters emit with a plain library
dump, unsorted and unquoted, and bolt reads those files without complaint. The
byte-identity requirement was asserted in the contract and not held in
production.

## Choosing a library

**The acceptance check is a round trip over the control-character fixture, run
with the adapters applied.** Without the adapters the check measures nothing a
pack does.

Three libraries were once listed here as losing data through their own emitters.
They do not. They lose it when the emitter is left to choose a scalar style,
because a single-quoted YAML scalar has no escape syntax at all: a control
character in one is written raw and reads back as a space. Quoting is adapter
two, and with it applied the same emitter escapes the same character correctly.
Measured over 73 code points, and directly:

    style left to the emitter    n: 'a<U+0085>  b'    reads back WRONG
    quoting adapter applied      "n": "a\Nb"          reads back CORRECT

That finding measured bare library calls, which is not how any pack uses a
library, and it condemned libraries for a fault in the harness. The libraries
are not named here because they were never the variable.

What the check is for: the adapters are four decisions, and a library that
escapes correctly under one style may not under another. Run the fixture through
the codec as the pack will call it, and a library that still loses a code point
is unfit. Run it bare and the answer is about nothing.

`docs/PATTERNS/adopting-a-library-for-a-codec.md` carries the procedure.

## Rows this changes

    FR-5.5   the fixture set holds packs level by canonical emission
             -> by structural agreement. The JSON Schema suite half is unchanged.
    FR-4.3   canonical form belongs to the save call
             -> kept. Each pack still has one output for one structure; it is
                no longer the same output as its siblings'.

`testdata/canonical/` is re-based from bytes to structures. The float, escaping
and quoting rules are unchanged and still stated, because they are properties of
meaning and not of layout.
