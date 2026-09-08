# The hand-written emitter was the thing that was wrong

`a-codec-emits-by-hand-when-libraries-disagree` says to write the emitter when
two libraries disagree, and gives TOML as the case that turned the YAML emitter
from a one-off into a rule. Measured again on 2026-09-07, both halves of that
turn out to be wrong, and the TOML emitter is not merely unnecessary. It is
incorrect.

## The TOML emitter writes a file it cannot read back

FR-2.4 says validation on the way out stops a caller writing a structure wrench
would refuse to read back, so a file produced by a save always survives a load.
It does not.

A nested table inside an array of tables loses its qualifying path:

    wrench canonical            tomli_w 1.2.0
    [[seq_of_maps]]             [[seq_of_maps]]

    [deep]                      [seq_of_maps.deep]
    deeper = ["a", 3.5]         deeper = ["a", 3.5]

`[deep]` is a top-level table. Read back, `deep` leaves the array entirely and
the array's second entry is `{}`.

    canonical round trips: False
    tomli_w round trips:   True

This is the exact hazard the codec's own docstring names: *"TOML binds a bare
key to the most recent header, so a scalar written after a section lands inside
it."* The emitter exists to control that hazard and falls into it. The library
does not.

Reproduce with `.ephemera/parity-toml.py`.

## The YAML emitter is replaceable by configuration

`ruamel.yaml` 0.19.1 emitted output **byte-identical** to the 207-line
hand-written emitter, across a 53-key tree carrying control characters, the
separators, unicode from four scripts, multiline strings, the int64 boundaries
and floats that want an exponent.

It took four adapters, none of which emits text:

    sort the keys                       a dict comprehension
    quote every string AND key          DoubleQuotedScalarString
    spell floats positionally           one representer, calling float_text
    write null as the word              one representer

Roughly 25 lines of configuration for 207 lines of emitter. **ruamel's escape
table already matched wrench's exactly**, including `\a`, `\x7F`, `\e`, `\0`,
`﻿` and `\L`. That part of the emitter was reimplementing something the
library had right.

Quoting keys is the one that is easy to miss: ruamel's own answer for a numeric
key is a single-quoted `'10'`, which is a third spelling again. It is fixed by
wrapping the key, not by writing an emitter.

## PyYAML loses data and that is a separate finding

`yaml.safe_dump` writes U+0085 raw, and reading it back folds it to a space.

    canonical -> 'before\x85after'
    pyyaml    -> 'before after'

Both the Python and Ruby packs detected it independently. FR-4.9 exists for
exactly this, and PyYAML violates it. Anything in the estate still writing with
`yaml.safe_dump` is exposed, and toolbox's adapters do.

## What the measurement says about the rule

The decision reasoned from an observation that was true: three TOML writers
produced three arrangements. What it concluded does not follow. The divergences
were **properties**, not formats, and every one is reachable by an adapter:
ordering, float spelling, quoting style, null spelling.

Writing a whole emitter to fix four properties is what put a round-trip defect
in the TOML codec, three times over, in a file long enough that nothing noticed.

**A library plus named adapters, or the format is not supported.** A format that
can only be served by hand-written emission is a format this project should
decline, because the emitter is where the defects live.

## What is not settled here

Byte-identity across packs was the requirement forcing all of this, and it is
worth asking separately whether it buys anything. The measurement says three of
four differently-written YAML files decode to one structure in both packs, and
the estate's own adapters already emit non-canonical YAML that bolt reads
without complaint. So the requirement is asserted in the contract and not held
in production.
