# Runbook

Binding wrench into a Go, Python or Rust project, what each pack is built
on, and where their output has to agree.

Setting the repositories up for the first time is covered once, in
`bolt/docs/runbook.md`: cloning the three as siblings and linking the shared
gate. This file assumes that is done.

## Bind it

Nothing is published to a registry yet, so every binding is a path. The relative
paths assume the sibling layout; use absolute ones if your checkout differs.

**Go**

    require github.com/scriptedworld/wrench/go v0.4.0
    replace github.com/scriptedworld/wrench/go => ../wrench/go

**Python**

    dependencies = ["wrench"]
    [tool.uv.sources]
    wrench = { path = "../wrench/python", editable = true }

**Rust**

    [dependencies]
    wrench = { version = "0.4.0", path = "../wrench/rust" }

## Use it

Each pack has one general pair and a convenience pair per format.

**Go**

    value, err := wrench.LoadYAMLFile(path, schema, reader)
    err := wrench.SaveYAMLFile(value, path, schema, writer)

`LoadJSONFile` and their `Save` counterparts likewise.
`LoadFormattedFile(path, schema, codec, reader)` takes the codec explicitly.

**Python**, as skid loads its config:

    SCHEMA = wrench.compile_schema("skid config", schemas.CONFIG)

    try:
        document = wrench.load_yaml_file(path, SCHEMA, wrench.LOCAL_FILE)
    except (wrench.ParseError, wrench.ValidationError) as exc:
        raise ValueError(f"config is present but not usable: {exc}") from exc

    wrench.save_yaml_file(document, path, SCHEMA, wrench.LOCAL_FILE)

`load_json_file`, `save_json_file` and so on. `wrench.LOCAL_FILE` is the
ready-made reader and writer for an ordinary file.

**Rust**, as bolt reads a jig:

    let value = wrench::load_formatted_file(
        path,
        &wrench::schemas::JIG,
        &wrench::YamlCodec,
        &wrench::LocalFileIo,
    )?;

`wrench::schemas` carries the shipped schemas; `wrench::compile_schema` builds
one from text.

A schema says what the document may contain. The reader and writer are where
bytes come from, which is what lets a caller test without a filesystem.

## Bytes that did not come from a file

A process's output, a network reply or a model's answer is validated the same
way a file is. Only the local file reader ships (FR-2.8), so hand the call a
reader that returns the bytes you already hold, and the path becomes the label
an error names:

    class Held:
        def __init__(self, data: bytes) -> None:
            self.data = data

        def read(self, path: str) -> bytes:
            return self.data

    verdicts = wrench.load_json_file("the model's reply", SCHEMA, Held(reply))

The bytes go through the same decode and the same validation as a file, so a
reply that does not match fails as `validate` and names where.

Finding the document inside surrounding prose is not wrench's job. Ask the
producer for the document alone. `claude -p --output-format json --json-schema
<schema>` returns an envelope whose `result` is the bare JSON text, and the
schema it is given must be an object at the top level: an array schema is
refused with an API 400. Validate `result` through the pack anyway, because a
schema the producer was told about is not a schema anything checked.

## What each pack is built on

The packs are not ports of each other. Each binds its own parsers and its own
JSON Schema validator, and each was written from the same contract.

| | Go | Python | Rust |
|---|---|---|---|
| schema | `santhosh-tekuri/jsonschema/v6` | `jsonschema` + `referencing` | `jsonschema` 0.52 |
| YAML | `go.yaml.in/yaml/v3` | `ruamel.yaml` | `yaml-rust2` reads, `libyaml-safer` writes |
| JSON | `encoding/json` | `json` | `serde_json` |

Independent implementations across three languages. None of them agrees
with the others about how to spell an ordinary value, and none raises an error
about it.

TOML was a fourth row and is retired: no maintained library in any of these
languages emits the canonical form wrench asked for, and the hand-written
emitters that stood in for one wrote a document they could not read back. If you
have TOML to read, read it with your language's own library and validate the
structure through wrench.

## Where the packs have to agree

Left alone, each engine writes what its own author preferred. These were
wrench's own packs, and every test passed:

| value | Go | Python | Rust |
|---|---|---|---|
| `1000000.0` | `1e+06` | `1000000.0` | `1000000.0` |
| `1e21` | `1e+21` | `1e+21` | `1000000000000000000000.0` |

Floats are the main one. Every pack now writes positional decimal, never an
exponent, with the shortest digits that read back as the same float, and a whole
number keeps its `.0` so it never reads back as an integer.

The rule carries no magnitude threshold on purpose. Any threshold has to be
stated in the contract and implemented identically in nine places; "never" is
the only version with nothing to get wrong. It is also the only version a
consumer parsing with a naive numeric pattern reads correctly, which is how the
defect was found: `1e+06` matched by `[0-9.]+` yields `1`. The cost is bounded
at 326 characters for a subnormal.

Control characters are escaped, never emitted raw.

Keys, quoting and null are the other three. Keys are sorted, every string and
every key is quoted so nothing changes type on the way back, and a null is
written as the word, not as an empty value.

Layout is not part of it. Two packs may indent a list differently or wrap a
long line in different places. What they are held to is that any pack's output
decodes to the same value in every other pack, because no canonical form exists
that every language's YAML library can emit.

Intent is not what holds it true. A shared fixture set in `testdata/canonical/`
is read by the Go, Python and Rust packs, and the suite-parity check refuses to
pass over an emptiness: pointed at a glob matching no files it exits 2 rather
than reporting success.

## How this repository gates itself, if yours has several packs

wrench is one repository holding three independent libraries, so the gate runs at
two levels and the split is deliberate.

Each pack gates itself. `just checks` runs `_each checks`, and every pack runs
the language jig for its own language plus the common one. A pack knows nothing
about its siblings.

The root runs what no pack can. `bin/test-suite-parity.py` fails when one pack's
suite covers something another's does not, and it reads them all at once. A
pack that could run it would have to know about its siblings, and the layering
is there so that no pack does.

    just checks        each pack, then the parity check
    just test          the suite in every pack
    just coverage      the same, with coverage

**A pack the recipes do not name is a pack that silently passes.** A directory
missing from `PACKS` in the `Justfile` is never run, and every recipe exits 0
having run nothing of it. Whatever fans out in your own repository, make the list
it fans over fail loudly when a directory is missing from it.

The coordination lives in the Justfile, not the jig. Bolt can compose
by running itself against a subdirectory and taking the verdict, and that is the
right tool when the subprojects are unlike each other. Here they are several
implementations of one contract, checked identically and then compared, so a
recipe that fans out and one check that fans in says it more plainly.

If your repository is one project, none of this applies: link the sets at the
root and run the jigs there.

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

**A float changing across a round trip** is a defect in wrench. Report it.
