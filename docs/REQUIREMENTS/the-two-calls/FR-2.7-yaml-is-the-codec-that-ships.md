# FR-2.7

| ID | Requirement | |
|---|---|---|
| FR-2.7 | Two codecs ship: YAML and JSON. The row began as YAML alone and is kept rather than retired, because the reason it gave is what held: the codec argument existed so that adding a format later would not be a change to the two calls, and adding one was not. | [A] |

## TOML was the third and is retired, 2026-09-07

Not because it was hard. Because no maintained library in any of the four
languages can emit wrench's canonical TOML, and the hand-written emitters that
existed instead were wrong.

**They write a document they cannot read back.** A sub-table inside an
array-of-tables entry is written with a root-relative header:

    [[a]]

    [b]
    c = 1

`[b]` binds at the document root, so `{"a": [{"b": {"c": 1}}]}` decodes back as
`{"a": [{}], "b": {"c": 1}}`. That breaks FR-2.4, which promises a file produced
by a save survives a load.

Run rather than read, in all three packs, each printing
`round trip identity: false`. The cause is the same line in each, recursion into
the entry with an empty path:

    rust/src/toml_codec.rs      write_table(out, entry.as_object()…, &[])
    python/wrench/toml_codec.py out.extend(_table(entry, []))
    go/toml.go                  tomlTable(out, entry.(map[string]any), nil)

The three packs' bytes are sha256-identical, so they agree byte for byte on a
document that is not the one they were given. The fixture set had no nested
table inside an array of tables, so nothing could see it. That is the failure
mode `packs-agree-on-structure-not-on-bytes` describes, arriving from the
direction nobody watched.

Every maintained library tested emits the correct header and round trips.

**Reaching canonical TOML from a library needs a tree-walking emitter**, which
is the thing being retired: BurntSushi's escape replacer and toml_edit's repr
setters are both private, so closing the gap means writing the escape table
again by hand.

TOML also cannot carry the value set. It has no null and no top-level scalar, so
every consumer needs a trimmed structure for it. It cost the most and expressed
the least.

Configuration files in this estate move to YAML. The ones that stay are the ones
other people's tools read: `pyproject.toml`, `Cargo.toml`, and the tool
configuration beside them.
