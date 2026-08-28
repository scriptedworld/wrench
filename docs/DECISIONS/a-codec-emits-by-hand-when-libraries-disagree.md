# A codec emits by hand when the libraries disagree

The YAML emitter was written by hand because no library produced wrench's bytes.
That read as a YAML-specific inconvenience until TOML shipped and turned out to
need exactly the same treatment, so it is a rule rather than a one-off.

**Take a library's emitter only after measuring it against the other packs.
Where two disagree, write the emitter.**

## What was measured

FACT 2026-08-28. The same structure, `{"b": 1, "a": {"z": [1, 2], "y": "x"}}`,
through each language's established TOML writer:

    tomli_w 1.2.0            z = [\n    1,\n    2,\n]   and no indent under [a]
    BurntSushi/toml 1.6.0    z = [1, 2]                 and two-space indent
    toml (Rust)              a third arrangement again

Three packs, three files, one structure. That is the failure `docs/PROJECT.md`
opens by saying wrench exists to prevent, and it would have shipped inside the
feature that was supposed to demonstrate the packs agreeing.

JSON went the other way and is worth recording as the contrast. `encoding/json`,
`json.dumps` and `serde_json` agree once sorting and indent are set, so all three
packs use their standard library and the output is byte-identical. Measured the
same day, same structure.

## So the rule is about the format, not the language

**A format with one obvious spelling can use its libraries. A format with
several needs an emitter.** JSON has one: sorted keys and two-space indent leave
nothing to choose. TOML has many, because a table can be a section or inline, an
array can be one line or several, and indentation under a header is a matter of
taste that every library settles differently.

That is knowable before writing code, by encoding one nested structure in each
language and diffing. It costs minutes and it is the check to run before
adopting any future codec.

## What the hand-written emitter costs, stated plainly

Roughly ninety lines per pack, three times, kept in step by tests asserting the
same bytes in all three suites. That is real and recurring: every change to
canonical form is three edits.

The alternative is worse and is not obviously worse, which is why this is
written down. Three libraries produce three files that are each valid, each
round-trip within their own pack, and pass every test a single-pack suite would
write. **Nothing inside one pack can see the divergence.** Only a cross-pack byte
comparison finds it, and only if somebody thinks to make one.

## The check that catches it

Encode one nested structure in each pack and diff the bytes. It found the TOML
divergence before any test existed:

    diff <(python) <(go) && diff <(python) <(rust)

`testdata/canonical/` does this for YAML by fixture. JSON and TOML assert the
same expected bytes inline in all three suites instead, which
`docs/PATTERNS/holding-two-packs-level.md` already names as the pattern.

## Related

The float divergence found the same day is the same shape one level down:
`repr`, `strconv.FormatFloat(v, 'g', -1, 64)` and `format!("{f}")` disagree about
when to use an exponent, so three packs spell `1000000.0` three ways *inside*
the YAML emitter they each wrote by hand.
`clank/tasks/wrench/parity/30-three-packs-spell-floats-three-ways` carries it,
and it is open. **A hand-written emitter removes the library's opinion and not
the language's**, which is the limit of this decision.
