# FR-5.5

| ID | Requirement | |
|---|---|---|
| FR-5.5 | Packs are held level by JSON Schema's own cross-implementation test suite, plus a shared fixture set covering **structural agreement** and error shape: any pack's output must decode to the same value in every other pack. Agreement comes from both being tested against the same declared cases, not from shared code. | [A] |

## It said canonical emission until 2026-09-07

The row asked every pack to emit the same bytes, and that is what forced a
hand-written emitter per format per pack. It cannot be kept, and the reason is
a measurement rather than a preference: **no canonical form exists that all four
libraries can emit.**

    libyaml, used by Rust    block sequences indentless, hard-coded
    yaml.v3, used by Go      block sequences indented, SetIndent is the only knob
    ruamel, used by Python   either
    Psych, used by Ruby      indentless

Whichever indentation the contract picks, one of Go or Rust cannot produce it,
and neither has an alternative worth having.

So the packs are held to what consumers actually depend on. Measured before the
row was changed, and it already held: four differently-shaped YAML files from
four independent emitters, each decoding to the same structure in both packs
that could be run against all of them.

**What did not change is the adapter set**, and it is where meaning is
preserved: keys sorted, every string and key quoted, floats spelled
positionally, null written as the word. Those are properties of the value, not
of the layout, and a pack that drops one produces a file that reads back
differently.

`docs/DECISIONS/packs-agree-on-structure-not-on-bytes.md` carries the argument
and the measurements.
