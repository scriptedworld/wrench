# Parity is reached by widening, never by refusing

Every pack treats the same input the same way and
produces the same output. Where they do not, the fix is to teach the laggards,
and **never** to narrow what wrench accepts so that the packs agree by handling
less.

## The rule

1. **Same input, same output, in every pack and every codec.** This is the
   property wrench exists for; a divergence is a defect rather than a
   preference.
2. **Widen where widening is cheap.** If one pack already handles a larger set
   correctly, the others learn from it. That is the good case and it costs
   nothing but the edit.
3. **Refusing to buy parity is the worst outcome available.** Limiting,
   filtering or warning a caller off a value *because wrench chose not to
   support it for parity* is the failure this decision names. A caller meets a
   restriction that exists for the library's convenience rather than for
   anything about their data.

## What it is not

**It does not forbid every refusal.** Two kinds survive, and the difference is
where the limit comes from:

    the FORMAT cannot express it      legitimate
    the PACKS would otherwise differ  forbidden by this decision

TOML has no null and no non-table root, so refusing those is the format speaking
and FR-4.7 already says so. NaN and the infinities have no JSON Schema
representation, so FR-4.1 refuses them. Neither is a parity shortcut.

The test to apply: **would this value be refused if there were only one pack?**
If yes, the limit is real. If no, it is this decision's target.

## What it settles today

**Control characters, `clank parity/50`.** The three options were escape, refuse,
or leave it per-format. Refusing is out by rule 3 and per-format is out by rule
1, so **the answer is escape**, and it is also rule 2's good case: Go's YAML
emitter is already correct across all 70 code points measured, and the other two
packs already read what it writes. Teaching two hand-written emitters a table
that can be read off a third is the whole of the work.

**Integers past int64, `clank parity/40`.** Widen to float rather than refuse,
which is the answer already given and which this rule confirms.

**It is also the one place the rule bites back, and that is worth stating.**
Widening an integer is lossy: Python round trips 2^64 exactly today and would
stop. So the packs agree by all being equally wrong rather than by all being
right, which is worse than the control-character case where everyone ends up
correct.

The alternative that keeps exactness is arbitrary precision, and it fails rule
2's word *simply*: `serde_json::Value` and Go's `any` would both need a new
numeric type, which is FR-2.9's decoded-value contract rather than an
implementation detail. So the lossy answer stands until somebody wants to pay
for the other one, and this paragraph is here so the next reader knows it was
priced rather than missed.

## Why this and not the reverse

Narrowing is the tempting fix because it is always available and always works:
refuse the awkward value and every pack agrees immediately. It moves the cost
from the library, which is one place and has maintainers, to every caller, which
is many places and has none.

It also degrades quietly. Each refusal is individually defensible and the set of
them is never reviewed, so a library that reaches parity by narrowing ends up
with a contract shaped by whichever pack was hardest to fix.

## How to apply it to the next format

A fourth codec, or a fifth language pack, meets this as a checklist:

- Enumerate the value space by type rather than by imagination, per
  `docs/LESSONS/a-fixture-set-agrees-about-the-values-somebody-thought-of.md`.
- Where packs differ, find the one that is right and copy it.
- Where none is right, define the output and make them all produce it.
- Where the format genuinely cannot hold the value, refuse it and say so in a
  requirement, so the limit is written down rather than discovered.
