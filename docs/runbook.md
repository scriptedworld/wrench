# Runbook

Binding wrench into a Go, Python or Rust project, what each pack is built on,
and where their output was forced to agree.

Setting the repositories up for the first time is covered once, in
`bolt/docs/runbook.md`: cloning the three as siblings and linking the shared
gate. This file assumes that is done.

## Bind it

Nothing is published to a registry yet, so every binding is a path. The relative
paths assume the sibling layout; use absolute ones if your checkout differs.

**Go**

    require github.com/scriptedworld/wrench/go v0.3.0
    replace github.com/scriptedworld/wrench/go => ../wrench/go

**Python**

    dependencies = ["wrench"]
    [tool.uv.sources]
    wrench = { path = "../wrench/python", editable = true }

**Rust**

    [dependencies]
    wrench = { version = "0.3.0", path = "../wrench/rust" }

## Use it

Each pack has one general pair and a convenience pair per format.

**Go**

    value, err := wrench.LoadYAMLFile(path, schema, reader)
    err := wrench.SaveYAMLFile(value, path, schema, writer)

`LoadJSONFile`, `LoadTOMLFile` and their `Save` counterparts likewise.
`LoadFormattedFile(path, schema, codec, reader)` takes the codec explicitly.

**Python**

    import wrench
    value = wrench.load_yaml_file(path, schema, reader)
    wrench.save_yaml_file(value, path, schema, writer)

`load_json_file`, `save_toml_file` and so on. `wrench.compile_schema` builds the
schema argument.

**Rust**

    let schema = wrench::compile_schema(name, text)?;
    let value = wrench::load_yaml_file(path, schema.as_ref(), &reader)?;

A schema says what the document may contain. The reader and writer are where
bytes come from, which is what lets a caller test without a filesystem.

## What each pack is built on

The packs are not ports of each other. Each binds its own parsers and its own
JSON Schema validator, and each was written from the same contract.

| | Go | Python | Rust |
|---|---|---|---|
| schema | `santhosh-tekuri/jsonschema/v6` | `jsonschema` + `referencing` | `jsonschema` 0.52 |
| YAML | `go.yaml.in/yaml/v3` | `PyYAML` | `yaml-rust2` |
| JSON | `encoding/json` | `json` | `serde_json` |
| TOML | `BurntSushi/toml` | `tomllib` | `toml` |

Nine parser implementations across three languages. **None of them agrees with
the others about how to spell an ordinary value**, and none raises an error
about it.

## Where the output was unified

Left alone, each engine writes what its own author preferred. These were
wrench's own three packs, and every test passed:

| value | Go | Python | Rust |
|---|---|---|---|
| `1000000.0` | `1e+06` | `1000000.0` | `1000000.0` |
| `1e21` | `1e+21` | `1e+21` | `1000000000000000000000.0` |

**Floats are the main one.** Every pack now writes positional decimal, never an
exponent, with the shortest digits that read back as the same float, and a whole
number keeps its `.0` so it never reads back as an integer.

The rule carries no magnitude threshold on purpose. Any threshold has to be
stated in the contract and implemented identically in nine places; "never" is
the only version with nothing to get wrong. It is also the only version a
consumer parsing with a naive numeric pattern reads correctly, which is how the
defect was found: `1e+06` matched by `[0-9.]+` yields `1`. The cost is bounded
at 326 characters for a subnormal.

**Control characters** are escaped in each format's own spelling rather than
emitted raw.

**What holds it true is not intent.** A shared fixture set in
`testdata/canonical/` is read by all three packs, and the property under test is
that the same document through any pack and any codec produces the same bytes.
The suite-parity check refuses to pass over an emptiness: pointed at a glob
matching no files it exits 2 rather than reporting success.

## Gate your project the same way

wrench does not gate your project; toolbox does, and wrench is one of its
adopters.

    python3 ../toolbox/bin/link-toolbox.py . common go
    bolt common-quality .
    bolt go-std-quality .

Take `common` plus your language's set. `common` includes the secrets scan.
`toolbox/README.md` covers what your project must supply, what a first run tends
to report, and writing a definitions file when a jig's defaults do not fit.

Check the links in CI:

    python3 ../toolbox/bin/link-toolbox.py --check . common go

It exits 1 on drift.

## When it goes wrong

**`the jig ... is unreadable`** means the links are absent. Run the linker; a
fresh clone has no gate until you do.

**A gate passing here and failing in your project** is usually the path rule: a
path travelling with the jig resolves against `{config_dir}`, a path belonging
to your project stays relative to your root.

**A float changing across a round trip** is the defect wrench exists to prevent.
Report it.
