"""Tests for the Python pack.

The canonical cases come from `testdata/canonical/`, the same directories the
Go pack is held to. That is the point of them: two implementations agreeing on
the schema and disagreeing on the bytes is the failure a shared fixture set
exists to catch, and neither pack is the oracle for the other.
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404 - registered in SUPPRESSIONS
import sys
from pathlib import Path

import pytest

import wrench

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "testdata" / "canonical"

CASES = sorted(p.name for p in FIXTURES.iterdir() if p.is_dir())


class Stub:
    """Bytes without a filesystem. Its existence is the point of FR-2.5a: a
    reader takes the path, so a test replaces the whole IO boundary."""

    def __init__(self, data: bytes = b"", error: Exception | None = None) -> None:
        """Bytes to hand back, or an error to raise instead of handing any."""
        self.data = data
        self.error = error
        self.saw_path: str | None = None
        self.written: bytes | None = None

    def read(self, path: str) -> bytes:
        """Record the path it was given, then answer. Recording is the point:
        several tests assert the call passes the path through untouched."""
        self.saw_path = path
        if self.error:
            raise self.error
        return self.data

    def write(self, path: str, data: bytes) -> None:
        """Capture the bytes rather than writing them, so a test can assert the
        writer never ran when validation or encoding should have stopped it."""
        self.saw_path = path
        if self.error:
            raise self.error
        self.written = data


ANYTHING = wrench.compile_schema(
    "anything.schema.json",
    '{"$schema": "https://json-schema.org/draft/2020-12/schema"}',
)

VALID_ENVELOPE = b"success: true\n"


# ---- the shared fixture set -------------------------------------------------


SHIPPED_BY_ID = {
    "https://scriptedworld.github.io/wrench/envelope.schema.json": "ENVELOPE_SCHEMA",
    "https://scriptedworld.github.io/wrench/jig.schema.json": "JIG_SCHEMA",
    "https://scriptedworld.github.io/wrench/manifest.schema.json": "MANIFEST_SCHEMA",
    "https://scriptedworld.github.io/wrench/definitions.schema.json": "DEFINITIONS_SCHEMA",
}


def declared_schema(case):
    """The shipped schema a fixture names in its `schema` file, or None where it
    names none. A fixture with no such file is a codec case and nothing more."""
    path = FIXTURES / case / "schema"
    if not path.exists():
        return None
    identifier = path.read_text().strip()
    assert identifier in SHIPPED_BY_ID, f"{case} declares {identifier}, which this pack does not ship"
    return getattr(wrench, SHIPPED_BY_ID[identifier])


# COVERS: FR-4.1, FR-4.2, FR-4.3, FR-4.4, FR-5.5, FR-5.6 | property
@pytest.mark.parametrize("case", CASES)
def test_canonical_form_matches_the_shared_fixtures(case):
    """The bytes this pack emits are the bytes the fixture declares. The Go
    pack is held to the same file."""
    directory = FIXTURES / case
    value = wrench.YAML.decode((directory / "input.yaml").read_bytes())
    assert wrench.YAML.encode(value).decode() == (directory / "canonical.yaml").read_text()

    # A fixture that is an instance of a shipped schema says so, and is held to
    # it. Byte-identical output between two packs says they agree on the
    # spelling; it does not say the thing they spelled is a document any
    # consumer would accept.
    schema = declared_schema(case)
    if schema is not None:
        schema.validate(value)


# COVERS: FR-3.8 | positive
def test_every_shipped_schema_has_an_instance_fixture():
    """A schema nothing is ever validated against is a schema nobody knows
    compiles, let alone accepts a real document. The directory is the authority
    on both sides, so a fifth schema fails here until it has a fixture."""
    declared = {}
    for path in sorted((ROOT / "schemas").glob("*.schema.json")):
        declared[json.loads(path.read_text())["$id"]] = False
    assert declared, "no shipped schemas, so this test asserts nothing"

    for case in CASES:
        path = FIXTURES / case / "schema"
        if not path.exists():
            continue
        identifier = path.read_text().strip()
        assert identifier in declared, f"fixture {case} declares {identifier}, which no schema does"
        declared[identifier] = True

    uncovered = sorted(i for i, seen in declared.items() if not seen)
    assert not uncovered, f"no fixture is an instance of: {', '.join(uncovered)}"


# COVERS: FR-4.5 | property
@pytest.mark.parametrize("case", CASES)
def test_canonical_form_is_a_fixed_point(case):
    """Encoding the canonical form returns it unchanged, or it was not
    canonical."""
    canonical = (FIXTURES / case / "canonical.yaml").read_bytes()
    assert wrench.YAML.encode(wrench.YAML.decode(canonical)) == canonical


# COVERS: FR-4.5 | property
def test_every_scalar_type_survives_the_round_trip():
    value = {
        "truth": True,
        "whole": 7,
        "partial": 2.5,
        "round": 3.0,
        "text": "no",
        "absent": None,
        "list": [1, "two", False],
    }
    back = wrench.YAML.decode(wrench.YAML.encode(value))
    assert back == value
    assert isinstance(back["round"], float), "a whole float read back as an integer"
    assert isinstance(back["text"], str), "a quoted string read back as something else"


# COVERS: FR-4.1 | negative
def test_a_value_with_no_canonical_form_is_refused():
    """An object with no YAML spelling. Refusing beats inventing one, the error
    says where the trouble was, and the writer never runs."""
    writer = Stub()

    with pytest.raises(wrench.EncodeError) as caught:
        wrench.save_formatted_file({"c": object()}, "f.yaml", ANYTHING, wrench.YAML, writer)

    assert 'at key "c"' in str(caught.value), "the error does not say where"
    assert writer.written is None, "the writer ran despite encoding failing"


# COVERS: FR-2.9 | regression
def test_a_timestamp_decodes_to_a_string_so_it_can_be_written_back():
    """YAML has a native timestamp type and JSON does not. Before this, an
    unquoted date decoded to a date object, reached the validator, which has no
    type for it, and then could not be encoded: wrench could read a file it could
    not write back."""
    value = wrench.YAML.decode(b"day: 2026-01-01\nstamp: 2026-01-01T07:32:00Z\n")

    for name in ("day", "stamp"):
        assert isinstance(value[name], str), f"{name} decoded to {type(value[name]).__name__}, want a string so it is a JSON value"

    # The point of the coercion: what was read can be written.
    encoded = wrench.YAML.encode(value)
    assert wrench.YAML.encode(wrench.YAML.decode(encoded)) == encoded, "not a fixed point"


# COVERS: FR-4.1 | edge
def test_nan_and_the_infinities_are_refused():
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(wrench.EncodeError):
            wrench.YAML.encode([value])


# ---- the two calls ----------------------------------------------------------


# COVERS: FR-2.1, FR-2.2 | positive
def test_load_returns_the_validated_structure():
    value = wrench.load_formatted_file("output.yaml", wrench.ENVELOPE_SCHEMA, wrench.YAML, Stub(VALID_ENVELOPE))
    assert value == {"success": True}


# COVERS: FR-2.5a | positive
def test_the_reader_is_handed_the_path():
    reader = Stub(VALID_ENVELOPE)
    wrench.load_formatted_file("nowhere/output.yaml", wrench.ENVELOPE_SCHEMA, wrench.YAML, reader)
    assert reader.saw_path == "nowhere/output.yaml"


# COVERS: FR-2.3 | negative
def test_a_call_with_no_schema_is_refused():
    with pytest.raises(wrench.UsageError, match="no schema"):
        wrench.load_formatted_file("f.yaml", None, wrench.YAML, Stub())
    with pytest.raises(wrench.UsageError, match="no schema"):
        wrench.save_formatted_file({}, "f.yaml", None, wrench.YAML, Stub())


# COVERS: FR-2.2 | negative
def test_a_call_with_no_codec_or_no_io_is_refused():
    with pytest.raises(wrench.UsageError, match="no codec"):
        wrench.load_formatted_file("f.yaml", ANYTHING, None, Stub())
    with pytest.raises(wrench.UsageError, match="no reader"):
        wrench.load_formatted_file("f.yaml", ANYTHING, wrench.YAML, None)
    with pytest.raises(wrench.UsageError, match="no writer"):
        wrench.save_formatted_file({}, "f.yaml", ANYTHING, wrench.YAML, None)


# COVERS: FR-2.6 | negative
def test_a_failure_says_which_step_failed():
    with pytest.raises(wrench.ReadError):
        wrench.load_formatted_file(
            "gone.yaml",
            wrench.ENVELOPE_SCHEMA,
            wrench.YAML,
            Stub(error=FileNotFoundError()),
        )

    with pytest.raises(wrench.ParseError):
        wrench.load_formatted_file(
            "f.yaml",
            wrench.ENVELOPE_SCHEMA,
            wrench.YAML,
            Stub(b"success: [unterminated\n"),
        )

    with pytest.raises(wrench.ValidationError):
        wrench.load_formatted_file("f.yaml", wrench.ENVELOPE_SCHEMA, wrench.YAML, Stub(b'success: "yes"\n'))


# COVERS: FR-2.4 | negative
def test_save_refuses_a_structure_it_would_not_read_back():
    writer = Stub()
    with pytest.raises(wrench.ValidationError):
        wrench.save_formatted_file({"success": "yes"}, "f.yaml", wrench.ENVELOPE_SCHEMA, wrench.YAML, writer)
    assert writer.written is None, "the writer ran despite validation failing"


# COVERS: FR-2.4, FR-4.3 | positive
def test_save_writes_canonical_form():
    writer = Stub()
    wrench.save_formatted_file(
        {"success": False, "reasons": [{"kind": "k", "message": "m"}]},
        "f.yaml",
        wrench.ENVELOPE_SCHEMA,
        wrench.YAML,
        writer,
    )
    assert writer.written.decode() == '"reasons":\n  - "kind": "k"\n    "message": "m"\n"success": false\n'


# ---- schemas ----------------------------------------------------------------


LOCATIONS = ("project_root", "base_dir", "work_dir", "config_dir", "output_dir")


def _manifest(**variables):
    """A manifest carrying the five locations bolt always supplies. Every
    variable is {value, from}, because a reader needs which layer won as well
    as what the value was."""
    supplied = {name: {"value": "/p", "from": "bolt"} for name in LOCATIONS}
    supplied.update(variables)
    return {
        "task": "build",
        "ordinal": 0,
        "command": "go build ./...",
        "variables": supplied,
    }


def _refuses(schema, value, what):
    """Assert a schema refuses a value, naming what was offered when it does
    not. `pytest.raises` alone loses which case of a table got through."""
    try:
        schema.validate(value)
    except (wrench.ValidationError, wrench.SchemaError):
        # Two distinct failures, both meaning the value did not get through: the
        # schema refused it, or the schema could not be used because a reference
        # would not resolve. Naming both keeps the helper from passing on a
        # ReadError, which a bare Error would.
        return
    pytest.fail(f"{what} was accepted")


# COVERS: FR-3.1, FR-3.2, FR-3.5 | positive
def test_all_four_shipped_schemas_load_from_the_one_copy():
    for schema in (
        wrench.ENVELOPE_SCHEMA,
        wrench.JIG_SCHEMA,
        wrench.MANIFEST_SCHEMA,
        wrench.DEFINITIONS_SCHEMA,
    ):
        assert isinstance(schema, wrench.Schema), f"{schema!r} is not a Schema"
    wrench.ENVELOPE_SCHEMA.validate({"success": True})
    wrench.JIG_SCHEMA.validate({"tasks": [{"name": "build", "command": "go build ./..."}]})
    wrench.MANIFEST_SCHEMA.validate(_manifest())
    wrench.DEFINITIONS_SCHEMA.validate({"requirements": "../REQUIREMENTS.md"})


# COVERS: FR-3.7, FR-5.7 | regression
def test_every_shipped_schema_is_exported():
    """A schema added to schemas/ and picked up by one pack but not the other is
    a divergence in the contract that nothing reports. It has happened: a fourth
    schema shipped, Go exported it, and this module named three filenames and did
    not. Each pack asserts against the directory, so both agreeing with the
    directory is what makes them agree with each other."""
    declared = {}
    for path in sorted((ROOT / "schemas").glob("*.schema.json")):
        document = json.loads(path.read_text())
        assert document.get("$id"), f"{path.name} declares no $id"
        declared[document["$id"]] = path.name

    exported = {}
    for name in wrench.__all__:
        candidate = getattr(wrench, name)
        if isinstance(candidate, wrench.Schema):
            exported[candidate.name] = name

    for identifier, filename in declared.items():
        assert identifier in exported, f"{filename} declares {identifier} and this pack exports no schema for it"

    for identifier in exported:
        assert identifier in declared, f"this pack exports {identifier} and no file in schemas/ declares it"


# COVERS: FR-3.1, FR-3.4 | edge
def test_a_manifest_variable_says_which_layer_supplied_it():
    """A bare value is the shape before three layers existed. It is refused, so
    a producer cannot write a manifest that loses which layer won."""
    wrench.MANIFEST_SCHEMA.validate(
        _manifest(
            requirements={"value": "../REQUIREMENTS.md", "from": "file"},
            all_paths={"value": ["a.go", "b.go"], "from": "bolt"},
        )
    )

    for what, variable in {
        "a bare value": "../REQUIREMENTS.md",
        "a value with no layer": {"value": "x"},
        "a layer with no value": {"from": "jig"},
        "a layer outside the three": {"value": "x", "from": "environment"},
    }.items():
        _refuses(wrench.MANIFEST_SCHEMA, _manifest(requirements=variable), what)


def _versioned():
    """The shipped schemas carrying a top-level version, with a document each
    that is otherwise valid. definitions is absent on purpose: it is an open
    mapping where every key is a placeholder name, so reserving one costs
    something the other three do not pay."""
    return {
        "envelope": (wrench.ENVELOPE_SCHEMA, b"success: true\n"),
        "jig": (wrench.JIG_SCHEMA, b'tasks:\n  - name: check\n    command: "true"\n'),
        "manifest": (wrench.MANIFEST_SCHEMA, _manifest_yaml()),
    }


def _manifest_yaml():
    lines = [b"task: build\n", b"ordinal: 0\n", b"command: go build\n", b"variables:\n"]
    lines.extend(f"  {name}:\n    value: /p\n    from: bolt\n".encode() for name in LOCATIONS)
    return b"".join(lines)


# COVERS: FR-3.9 | edge
def test_a_format_may_declare_the_version_it_conforms_to():
    """Optional, because every document written before the field existed carries
    none and claiming nothing is the honest reading of that. Present, it is
    semver, so a consumer can refuse a major rather than failing later on a field
    it cannot find."""
    accepted = [
        "1.0.0",
        "0.1.0",
        "10.20.30",
        "1.0.0-alpha.1",
        "1.0.0+build.5",
        "1.0.0-rc.1+build.5",
    ]
    refused = ["1", "1.0", "v1.0.0", "1.0.0.0", "01.0.0", "", "latest", "1.0.0-"]

    for name, (schema, rest) in _versioned().items():
        # Absent is valid, which is what makes the field additive.
        wrench.load_formatted_file("f.yaml", schema, wrench.YAML, Stub(rest))

        for version in accepted:
            document = f'version: "{version}"\n'.encode() + rest
            wrench.load_formatted_file("f.yaml", schema, wrench.YAML, Stub(document))

        for version in refused:
            document = f'version: "{version}"\n'.encode() + rest
            try:
                wrench.load_formatted_file("f.yaml", schema, wrench.YAML, Stub(document))
            except wrench.ValidationError:
                continue
            pytest.fail(f"{name}: version {version!r} was accepted and is not semver")

        # A bare number is the mistake this pattern exists to catch: YAML reads
        # 1.0 as a float, and a float is not a version.
        try:
            wrench.load_formatted_file("f.yaml", schema, wrench.YAML, Stub(b"version: 1.0\n" + rest))
        except wrench.ValidationError:
            continue
        pytest.fail(f"{name}: an unquoted 1.0 was accepted, so a float passed as a version")


# COVERS: FR-3.9 | property
def test_the_version_field_is_the_same_in_every_format_that_carries_it():
    """Written into each schema rather than referenced, because it constrains a
    scalar rather than describing a shape, and a shipped schema exists to be an
    instance of something. Repetition is the cost, so drift is what this checks."""
    seen = {}
    for path in sorted((ROOT / "schemas").glob("*.schema.json")):
        properties = json.loads(path.read_text()).get("properties") or {}
        if "version" in properties:
            seen[path.name] = properties["version"]

    assert seen, "no shipped schema declares a version field, so this asserts nothing"
    first = next(iter(seen))
    for name, block in seen.items():
        assert block == seen[first], f"the version field in {name} differs from the one in {first}"


# COVERS: FR-3.1, FR-3.3, FR-3.6 | positive
def test_a_jigs_definitions_block_is_held_to_the_shared_shape():
    """The block and the file are one shape, written once and referenced across
    two shipped schemas. A jig carrying a nested value has to be refused by a
    rule the jig schema does not itself state, which is what proves the
    reference between them resolved."""
    flat = b'definitions:\n  requirements: REQUIREMENTS.md\n  line_length: 100\ntasks:\n  - name: check\n    command: "true"\n'
    wrench.load_formatted_file("bolt.q.yaml", wrench.JIG_SCHEMA, wrench.YAML, Stub(flat))

    nested = b'definitions:\n  python:\n    line_length: 100\ntasks:\n  - name: check\n    command: "true"\n'
    with pytest.raises(wrench.ValidationError):
        wrench.load_formatted_file("bolt.q.yaml", wrench.JIG_SCHEMA, wrench.YAML, Stub(nested))


# COVERS: FR-3.1, FR-3.4 | edge
def test_a_jig_may_declare_it_stands_at_the_repository_root():
    """The field reaches the working directory and nothing else. The walk, the
    containment, the filter patterns and {base_dir} stay what the caller
    granted, which is why it is a boolean on the jig rather than a base a jig
    task can be talked into widening."""
    tasks = b'tasks:\n  - name: check\n    command: "true"\n'

    for declared in (
        b"needs-repository-root: true\n",
        b"needs-repository-root: false\n",
        b"",
    ):
        wrench.load_formatted_file("bolt.q.yaml", wrench.JIG_SCHEMA, wrench.YAML, Stub(declared + tasks))

    refused = {
        "a string": b'needs-repository-root: "true"\n',
        "a number": b"needs-repository-root: 1\n",
        "an empty key": b"needs-repository-root:\n",
    }
    for what, declared in refused.items():
        try:
            wrench.load_formatted_file("bolt.q.yaml", wrench.JIG_SCHEMA, wrench.YAML, Stub(declared + tasks))
        except wrench.ValidationError:
            continue
        pytest.fail(f"{what} was accepted as needs-repository-root")

    # It is the jig's, not a jig task's. A tool needing the root needs it
    # wherever it is placed, so a caller cannot grant it per placement.
    on_task = b"tasks:\n  - name: child\n    jig: other\n    needs-repository-root: true\n"
    with pytest.raises(wrench.ValidationError):
        wrench.load_formatted_file("bolt.q.yaml", wrench.JIG_SCHEMA, wrench.YAML, Stub(on_task))


def _consumer_schema(target):
    """A caller's own schema whose one property references the target, which is
    what an adapter extending a shipped schema would write."""
    return json.dumps(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"d": {"$ref": target}},
        }
    )


# COVERS: FR-3.10 | positive
def test_a_consumer_schema_may_reference_a_shipped_one():
    """The case a consumer most wants: an adapter extending the envelope schema
    references it rather than copying it, and a copy is the drift FR-3.2 exists
    to prevent."""
    schema = wrench.compile_schema(
        "mine.schema.json",
        _consumer_schema("https://scriptedworld.github.io/wrench/definitions.schema.json"),
    )

    schema.validate({"d": {"a": "x"}})

    # A nested value is refused by a rule only the referenced schema states, so
    # a refusal here is what proves the reference resolved rather than being
    # skipped.
    _refuses(
        schema,
        {"d": {"a": {"b": 1}}},
        "a nested value, so the reference did not resolve",
    )


# COVERS: FR-3.10 | negative
def test_a_schema_may_reference_nothing_outside_the_shipped_set(tmp_path):
    """Measured before this existed: a file:// reference loaded that file off
    disk, so a schema's meaning depended on files outside it. Nothing was ever
    fetched over the network."""
    local = tmp_path / "local.schema.json"
    local.write_text('{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"string"}')

    targets = {
        "a file url": f"file://{local}",
        "an absolute path": str(local),
        "a relative path": "local.schema.json",
        "an http url": "http://example.com/x.schema.json",
        "an https url": "https://example.com/x.schema.json",
        "an unshipped wrench": "https://scriptedworld.github.io/wrench/not-shipped.schema.json",
    }
    for target in targets.values():
        schema = wrench.compile_schema("mine.schema.json", _consumer_schema(target))
        # ValueError specifically, which is what Schema.validate raises for a
        # reference it cannot resolve. Catching Exception here would pass on a
        # typo in this test as readily as on the refusal it is checking for.
        # `what` and `target` are in the failure's locals when one does resolve.
        with pytest.raises(wrench.SchemaError):
            schema.validate({"d": "anything"})


# COVERS: FR-3.10 | edge
def test_the_environment_can_restore_external_references(tmp_path):
    """An escape hatch nobody exercises is one that may not work. This asserts
    the hatch opens, not that opening it is a good idea.

    os.environ directly rather than monkeypatch: this arranges an input, and
    reaching for a patching fixture to do it blurs the line with mocking the
    code under test, which is not allowed here without asking."""
    from wrench.schema import ALLOW_EXTERNAL_REFS

    local = tmp_path / "local.schema.json"
    local.write_text('{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"string"}')
    document = _consumer_schema(f"file://{local}")

    _refuses(
        wrench.compile_schema("mine.schema.json", document),
        {"d": "anything"},
        "a file reference with the variable unset",
    )

    previous = os.environ.get(ALLOW_EXTERNAL_REFS)
    os.environ[ALLOW_EXTERNAL_REFS] = "1"
    try:
        wrench.compile_schema("mine.schema.json", document).validate({"d": "anything"})
    finally:
        if previous is None:
            del os.environ[ALLOW_EXTERNAL_REFS]
        else:
            os.environ[ALLOW_EXTERNAL_REFS] = previous


# COVERS: FR-3.10 | edge
def test_a_caller_cannot_redefine_a_shipped_schema():
    """Registering a shipped id twice would let a document decide what the
    envelope schema means, which is the one thing a shipped schema fixes."""
    for path in sorted((ROOT / "schemas").glob("*.schema.json")):
        identifier = json.loads(path.read_text())["$id"]
        try:
            wrench.compile_schema(
                identifier,
                '{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"string"}',
            )
        except wrench.SchemaError:
            continue
        pytest.fail(f"{identifier} was redefined by a caller")


# COVERS: FR-3.2, FR-3.3 | negative
def test_a_definitions_file_takes_one_level_of_scalars():
    scalars = b'requirements: ../REQUIREMENTS.md\nline_length: 100\nstrict: true\nempty: ""\n'
    wrench.load_formatted_file("d.yaml", wrench.DEFINITIONS_SCHEMA, wrench.YAML, Stub(scalars))

    refused = {
        "a list value": b"tags:\n  - one\n  - two\n",
        "a nested value": b"python:\n  line_length: 100\n",
        "a hyphenated name": b"line-length: 100\n",
        "a name with a brace": b'"{line_length}": 100\n',
        "a leading underscore": b"_leading: 1\n",
    }
    for what, document in refused.items():
        try:
            wrench.load_formatted_file("d.yaml", wrench.DEFINITIONS_SCHEMA, wrench.YAML, Stub(document))
        except wrench.ValidationError:
            continue
        pytest.fail(f"{what} was accepted")


# COVERS: FR-3.2 | regression
def test_a_validation_error_names_the_schema_by_id_not_by_local_path():
    """The identifier lands in the error, the error lands in a reason, and a
    reason travels as evidence."""
    with pytest.raises(wrench.ValidationError) as caught:
        wrench.load_formatted_file("f.yaml", wrench.ENVELOPE_SCHEMA, wrench.YAML, Stub(b'success: "yes"\n'))
    message = str(caught.value)
    assert "scriptedworld.github.io/wrench/envelope.schema.json" in message
    assert str(ROOT) not in message, "the error carries a local filesystem path"


# COVERS: FR-3.3 | property
def test_validation_is_indifferent_to_serialisation():
    block = b"success: false\nreasons:\n  - kind: k\n    message: m\n"
    flow = b"{success: false, reasons: [{kind: k, message: m}]}\n"
    for data in (block, flow):
        wrench.load_formatted_file("f.yaml", wrench.ENVELOPE_SCHEMA, wrench.YAML, Stub(data))


# COVERS: FR-3.4 | edge
def test_a_schema_checks_shape_and_not_meaning():
    """A reason whose message is empty is the right type and says nothing."""
    wrench.load_formatted_file(
        "f.yaml",
        wrench.ENVELOPE_SCHEMA,
        wrench.YAML,
        Stub(b'success: false\nreasons:\n  - kind: k\n    message: ""\n'),
    )


# COVERS: FR-1.2 | negative
def test_a_mapping_key_that_is_not_a_string_is_refused():
    with pytest.raises(wrench.ParseError):
        wrench.load_formatted_file("f.yaml", ANYTHING, wrench.YAML, Stub(b"1: one\n"))


# ---- the filesystem ---------------------------------------------------------


# COVERS: FR-2.1, FR-6.3 | positive
def test_round_trip_through_the_real_filesystem(tmp_path):
    path = str(tmp_path / "output.yaml")
    value = {"success": True, "metadata": {"statistics": {"checked": 12}}}

    wrench.save_formatted_file(value, path, wrench.ENVELOPE_SCHEMA, wrench.YAML, wrench.LOCAL_FILE)
    back = wrench.load_formatted_file(path, wrench.ENVELOPE_SCHEMA, wrench.YAML, wrench.LOCAL_FILE)

    assert back == value
    assert back["metadata"]["statistics"]["checked"] == 12


# COVERS: FR-2.1, FR-6.3 | positive
def test_a_path_object_is_accepted_and_normalised(tmp_path):
    """A Python caller passes `pathlib.Path`, and the annotation once said `str`.
    It ran correctly and a consumer type-checking against the pack got four
    errors on calls that worked, so the annotation was narrower than the
    contract.

    The seam still sees a string: `saw` is what the substituted writer was
    handed, and a reader or writer that had to accept both types would be paying
    for the caller's convenience.
    """
    target = tmp_path / "output.yaml"
    value = {"success": True}
    saw = []

    class RecordingWriter:
        def write(self, path, data):
            saw.append(path)
            wrench.LOCAL_FILE.write(path, data)

    wrench.save_formatted_file(value, target, wrench.ENVELOPE_SCHEMA, wrench.YAML, RecordingWriter())
    back = wrench.load_formatted_file(target, wrench.ENVELOPE_SCHEMA, wrench.YAML, wrench.LOCAL_FILE)

    assert back == value
    assert saw == [str(target)], "the writer was handed something other than a string"


# COVERS: FR-2.11 | negative
def test_a_path_that_is_neither_string_nor_pathlike_is_a_usage_error():
    """Refused before any file is touched, so it is `usage` and not `read`.
    Reaching the reader it would surface as a filesystem failure and send
    somebody looking at the disk for a caller's mistake."""
    with pytest.raises(wrench.UsageError) as caught:
        wrench.load_formatted_file(42, wrench.ENVELOPE_SCHEMA, wrench.YAML, wrench.LOCAL_FILE)

    assert caught.value.step == "usage"
    assert "int" in str(caught.value)


# COVERS: FR-2.8, FR-6.3 | positive
def test_local_file_writes_atomically(tmp_path):
    path = tmp_path / "output.yaml"
    path.write_bytes(b"previous\n")

    wrench.LOCAL_FILE.write(str(path), b"next\n")

    assert path.read_bytes() == b"next\n"
    assert list(tmp_path.iterdir()) == [path], "a temporary was left behind"


# COVERS: FR-6.3 | edge
def test_a_written_file_is_readable_by_its_consumers(tmp_path):
    """mkstemp makes a file only its owner can read. Evidence meant to be
    handed around has to survive being handed around."""
    path = tmp_path / "output.yaml"
    wrench.LOCAL_FILE.write(str(path), b"success: true\n")
    assert path.stat().st_mode & 0o777 == 0o644


# ---- reaching the library ---------------------------------------------------


# COVERS: FR-6.1 | positive
def test_the_pack_is_importable_without_an_install():
    """A fresh interpreter, given only the path to the package, imports it. No
    pip, no virtualenv, nothing that can be half present."""
    result = subprocess.run(  # nosec B603 - registered in SUPPRESSIONS
        [sys.executable, "-c", "import wrench; print(wrench.YAML)"],
        cwd=str(ROOT),
        env={"PYTHONPATH": str(ROOT / "python"), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        # The return code IS the assertion below, so a non-zero one must reach
        # it rather than raising here.
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "YAMLCodec" in result.stdout


# COVERS: FR-6.2 | positive
def test_yaml_support_is_whatever_the_platform_supplies():
    """It imports `yaml` by name rather than vendoring one, so Debian's
    python3-yaml satisfies it and so does a pip-installed PyYAML."""
    import yaml

    source = (ROOT / "python" / "wrench" / "codec.py").read_text()
    assert "import yaml" in source
    assert not (ROOT / "python" / "wrench" / "yaml").exists(), "a vendored copy"
    assert yaml.safe_load("a: 1") == {"a": 1}


# ---- rows the Go pack held alone --------------------------------------------
#
# One contract, two packs. A row exercised in one pack is a row the other can
# break silently, which is not hypothetical here: a schema change once landed
# green in Go because the only test of that schema was in this file.


# COVERS: FR-3.1 | negative
def test_an_unusable_schema_fails_when_it_is_compiled():
    """A schema that will not compile fails at the call that compiled it, so the
    failure does not surface later and somewhere else."""
    for document in {
        "not json": "{ not json at all",
        "not a schema": '{"type": 42}',
    }.values():
        # Both cases USED to raise a third-party type, json's JSONDecodeError
        # and jsonschema's SchemaError, and this test asserted them to document
        # the leak rather than hide it. FR-2.11 closed it: a caller does not
        # need to know which JSON parser or which validator wrench binds.
        #
        # The cause stays reachable, which is what makes the wrap honest rather
        # than a way of losing what happened.
        with pytest.raises(wrench.SchemaError) as caught:
            wrench.compile_schema("broken.schema.json", document)
        assert caught.value.__cause__ is not None, "the wrap discarded the cause"


# COVERS: FR-3.1 | negative
def test_a_manifest_keeps_the_five_locations():
    """Every execution has them whatever else it has, so a manifest missing one
    is not a smaller manifest, it is a broken one."""
    for missing in LOCATIONS:
        variables = {name: {"value": "/p", "from": "bolt"} for name in LOCATIONS if name != missing}
        _refuses(
            wrench.MANIFEST_SCHEMA,
            {
                "task": "build",
                "ordinal": 0,
                "command": "go build ./...",
                "variables": variables,
            },
            f"a manifest without {missing}",
        )


# COVERS: FR-6.3 | negative
def test_a_failed_write_leaves_no_temporary_behind(tmp_path):
    """The temporary is what atomicity is built on, so a write that fails before
    it starts must not leave one for somebody to find."""
    not_a_dir = tmp_path / "file"
    not_a_dir.write_bytes(b"")

    with pytest.raises(OSError):
        wrench.LOCAL_FILE.write(str(not_a_dir / "output.yaml"), b"x\n")

    entries = list(tmp_path.iterdir())
    assert entries == [not_a_dir], f"directory holds {entries}, want only the seeded file"


# COVERS: FR-1.1 | positive
def test_the_pack_reads_the_one_copy_of_the_schemas():
    """The schemas and a library for each language live in one repository, so a
    Go producer and a Python producer work from the same definition. The pack
    carries their text rather than resolving a path, so what makes that true is
    the carried copy being byte for byte the directory's."""
    from wrench._shipped import SHIPPED
    from wrench.schema import SCHEMA_DIR

    assert SCHEMA_DIR == ROOT / "schemas", "the test is measuring against a copy"
    on_disk = {p.name: p.read_text() for p in SCHEMA_DIR.glob("*.schema.json")}
    assert on_disk, "no schemas found where every pack takes them from"

    assert on_disk == SHIPPED, "the generated copy has drifted from schemas/"

    package = ROOT / "python" / "wrench"
    assert not list(package.glob("*.schema.json")), "a second copy beside the package"


# COVERS: FR-1.4 | negative
def test_an_envelope_missing_success_is_refused():
    """Validation is JSON Schema over the decoded structure, and wrench does not
    get to differ from that decision. It is where it is implemented."""
    with pytest.raises(wrench.ValidationError) as caught:
        wrench.load_formatted_file("output.yaml", wrench.ENVELOPE_SCHEMA, wrench.YAML, Stub(b"reasons: []\n"))
    assert "success" in str(caught.value), "the error does not name the missing key"


# COVERS: FR-2.5, FR-2.7 | positive
def test_codec_and_io_are_independent():
    """The same codec with two different readers. Neither combination needs a
    function of its own, which is what declaring them separately buys."""
    readers = {
        "first": Stub(VALID_ENVELOPE),
        "second": Stub(b"success: false\nreasons:\n  - kind: k\n    message: m\n"),
    }
    for name, reader in readers.items():
        envelope = wrench.load_formatted_file("output.yaml", wrench.ENVELOPE_SCHEMA, wrench.YAML, reader)
        assert "success" in envelope, f"the {name} reader produced no envelope"

    # Three codecs ship. The argument existed so adding one later would not be a
    # change to the two calls, and adding two was not: the calls above are the
    # ones they were before FR-2.7 was restated.
    assert isinstance(wrench.YAML, wrench.YAMLCodec)
    # `Codec` is the seam the three implement, which Go and Rust also export,
    # so it is excluded here rather than counted as a fourth shipped format.
    assert sorted(n for n in wrench.__all__ if n.endswith("Codec") and n != "Codec") == [
        "JSONCodec",
        "TOMLCodec",
        "YAMLCodec",
    ]
    assert {"Codec", "Reader", "Writer"} <= set(wrench.__all__), "a seam the other packs name is not exported"


# COVERS: FR-5.2 | property
def test_validation_is_a_real_json_schema_implementation():
    """$ref resolution, $defs and conditional application are the parts a
    hand-written checker never gets right. Binding to an established
    implementation means they work, and this is what that buys."""
    document = """{
      "$schema": "https://json-schema.org/draft/2020-12/schema",
      "type": "object",
      "properties": { "items": { "type": "array", "items": { "$ref": "#/$defs/entry" } } },
      "$defs": { "entry": { "type": "object", "required": ["id"], "properties": { "id": { "type": "integer" } } } }
    }"""
    schema = wrench.compile_schema("refs.schema.json", document)

    schema.validate({"items": [{"id": 1}]})

    _refuses(
        schema,
        {"items": [{"id": "one"}]},
        "a $ref'd constraint, so the reference did not resolve",
    )


# COVERS: FR-3.1, FR-3.4 | edge
def test_a_task_may_allow_an_empty_selection():
    """An empty selection is a failure by default, because a pattern matching
    nothing is far more often a stale path than a deliberate one. A task says
    otherwise for itself, and only where there is a selection to be empty: a
    command naming neither path variable has none, and a jig task has none
    either because emptiness is its child's business."""
    accepted = {
        "one execution per path": b'tasks:\n  - name: check\n    command: jq . {each_path}\n    matching: ["*.json"]\n    allow-empty: true\n',
        "one over the whole set": b'tasks:\n  - name: check\n    command: jq . {all_paths}\n    matching: ["*.json"]\n    allow-empty: true\n',
        "declining it explicitly": b"tasks:\n  - name: check\n    command: go test ./...\n    allow-empty: false\n",
        "omitting it": b"tasks:\n  - name: check\n    command: go test ./...\n",
    }
    for what, document in accepted.items():
        try:
            wrench.load_formatted_file("bolt.q.yaml", wrench.JIG_SCHEMA, wrench.YAML, Stub(document))
        except wrench.ValidationError as problem:  # pragma: no cover - failure path
            pytest.fail(f"{what} was refused: {problem}")

    refused = {
        "a command with no selection to be empty": b"tasks:\n  - name: check\n    command: go test ./...\n    allow-empty: true\n",
        "a jig task, whose child owns emptiness": b"tasks:\n  - name: child\n    jig: other\n    allow-empty: true\n",
    }
    for what, document in refused.items():
        try:
            wrench.load_formatted_file("bolt.q.yaml", wrench.JIG_SCHEMA, wrench.YAML, Stub(document))
        except wrench.ValidationError:
            continue
        pytest.fail(f"{what} was accepted")


# ---- the other two codecs ---------------------------------------------------
#
# The expected bytes below are asserted identically in all three suites. A table
# that differs between packs is packs that differ, which is the whole argument of
# docs/PATTERNS/holding-two-packs-level.md.

THREE_FORMATS = {"b": 1, "a": {"z": [1, 2], "y": "x"}, "d": True}

CANONICAL_JSON = b'{\n  "a": {\n    "y": "x",\n    "z": [\n      1,\n      2\n    ]\n  },\n  "b": 1,\n  "d": true\n}\n'

CANONICAL_TOML = b'b = 1\nd = true\n\n[a]\ny = "x"\nz = [1, 2]\n'


# COVERS: FR-2.7, FR-4.6 | property
def test_json_canonical_form():
    """Two-space indent, one key to a line, keys sorted, trailing newline. The
    same bytes the Go and Rust packs emit for this structure."""
    assert wrench.JSON.encode(THREE_FORMATS) == CANONICAL_JSON
    assert wrench.JSON.decode(CANONICAL_JSON) == THREE_FORMATS


# COVERS: FR-2.7, FR-4.7 | property
def test_toml_canonical_form():
    """Scalars first and sorted, then each sub-table as a section, arrays
    inline, no indentation."""
    assert wrench.TOML.encode(THREE_FORMATS) == CANONICAL_TOML
    assert wrench.TOML.decode(CANONICAL_TOML) == THREE_FORMATS


# COVERS: FR-4.7 | edge
def test_toml_writes_an_array_of_tables_as_repeated_sections():
    """The most ordinary shape in a hand-written config, and the one TOML has no
    inline spelling for. Found by the skid session round-tripping a real config
    while this row was still being written: the emitter sent every array down the
    inline path, so `[[x]]` had no route at all."""
    value = {
        "name": "x",
        "substitution": [
            {"kind": "literal", "pattern": "kokoro"},
            {"kind": "regex", "pattern": "skid"},
        ],
    }
    encoded = wrench.TOML.encode(value)
    assert encoded == (
        b'name = "x"\n\n[[substitution]]\nkind = "literal"\npattern = "kokoro"\n\n[[substitution]]\nkind = "regex"\npattern = "skid"\n'
    )
    assert wrench.TOML.decode(encoded) == value

    # An empty array is not a table array, whatever it would have held.
    assert wrench.TOML.encode({"a": []}) == b"a = []\n"


# COVERS: FR-4.7 | negative
def test_toml_refuses_a_null():
    """TOML cannot spell null, and substituting one would invent a document
    nobody wrote. The message names where it sits."""
    with pytest.raises(wrench.EncodeError) as caught:
        wrench.TOML.encode({"a": {"b": None}})
    assert "a.b" in str(caught.value)


# COVERS: FR-4.7 | edge
def test_toml_refuses_a_document_that_is_not_a_table():
    """There is no top-level scalar or array in TOML, so wrapping one in an
    invented key is the alternative and is worse."""
    with pytest.raises(wrench.EncodeError):
        wrench.TOML.encode([1, 2])


# COVERS: FR-4.7 | regression
def test_toml_temporal_types_decode_to_iso_strings():
    """FR-2.9 applied to the second format with native dates. Each spelling is
    what the type it was read as prints, so a date does not become a datetime."""
    value = wrench.TOML.decode(b"d = 2026-01-01\ndt = 2026-01-01T07:32:00Z\n")
    assert value["d"] == "2026-01-01"
    assert value["dt"].startswith("2026-01-01T07:32:00")


# COVERS: FR-2.10 | positive
def test_a_wrapper_per_format_supplies_the_codec():
    """The wrappers add no behaviour. Each is the core call with one argument
    filled in, and validation still runs."""
    writer = Stub()
    wrench.save_json_file({"success": True}, "out.json", wrench.ENVELOPE_SCHEMA, writer)
    assert writer.written == b'{\n  "success": true\n}\n'

    reader = Stub(b'{"success": true}')
    assert wrench.load_json_file("out.json", wrench.ENVELOPE_SCHEMA, reader) == {"success": True}

    toml_writer = Stub()
    wrench.save_toml_file({"success": True}, "out.toml", wrench.ENVELOPE_SCHEMA, toml_writer)
    assert toml_writer.written == b"success = true\n"

    yaml_writer = Stub()
    wrench.save_yaml_file({"success": True}, "out.yaml", wrench.ENVELOPE_SCHEMA, yaml_writer)
    assert yaml_writer.written == b'"success": true\n'


# COVERS: FR-2.10 | negative
def test_a_wrapper_still_validates():
    """The codec is filled in; the schema is not. A wrapper that skipped
    validation would be a way round FR-2.2."""
    writer = Stub()
    with pytest.raises(wrench.ValidationError):
        wrench.save_json_file({"success": "yes"}, "out.json", wrench.ENVELOPE_SCHEMA, writer)
    assert writer.written is None


# The float spellings below are asserted identically in all three suites. A table
# that differs between packs is packs that differ.
CANONICAL_FLOATS = [
    (1000000.0, "1000000.0"),
    (48.0, "48.0"),
    (123456789.0, "123456789.0"),
    (0.1, "0.1"),
    (1e16, "10000000000000000.0"),
    (1e21, "1000000000000000000000.0"),
    (1e-5, "0.00001"),
    (1e-7, "0.0000001"),
    (1.2345678901234567, "1.2345678901234567"),
    (-0.0, "-0.0"),
]

CANONICAL_FLOAT_CODECS: list[tuple[wrench.YAMLCodec | wrench.JSONCodec | wrench.TOMLCodec, str, str]] = [
    (wrench.YAML, '"n": ', "\n"),
    (wrench.JSON, '{\n  "n": ', "\n}\n"),
    (wrench.TOML, "n = ", "\n"),
]


# COVERS: FR-4.8 | property
@pytest.mark.parametrize(("value", "spelled"), CANONICAL_FLOATS)
def test_a_float_has_one_spelling_in_every_codec(value: float, spelled: str) -> None:
    """Positional decimal, never an exponent, in all three codecs.

    Each language's default float formatting picks its own threshold for
    switching to an exponent, and the three disagreed. A consumer matching a
    number with a naive pattern reads `1e+06` as 1, so the spelling is the
    contract's rather than the standard library's.
    """
    for codec, prefix, suffix in CANONICAL_FLOAT_CODECS:
        assert codec.encode({"n": value}) == (prefix + spelled + suffix).encode()


# The escape spellings below are asserted identically in all three suites. A
# table that differs between packs is packs that differ.
CANONICAL_ESCAPES = [
    (0x00, r"\0", r"\u0000"),
    (0x07, r"\a", r"\u0007"),
    (0x08, r"\b", r"\b"),
    (0x09, r"\t", r"\t"),
    (0x0B, r"\v", r"\u000B"),
    (0x1B, r"\e", r"\u001B"),
    (0x7F, r"\x7F", r"\u007F"),
    (0x85, r"\N", "\u0085"),
    (0x9F, r"\x9F", "\u009f"),
    (0x2028, r"\L", "\u2028"),
    (0x2029, r"\P", "\u2029"),
]


# COVERS: FR-4.9 | property
@pytest.mark.parametrize(("point", "in_yaml", "in_toml"), CANONICAL_ESCAPES)
def test_a_control_character_is_escaped_in_every_codec(point, in_yaml, in_toml):
    """Escaped rather than written raw, in each format's own spelling.

    A raw control character is refused by a strict YAML reader, accepted by a
    lenient one, and folded to a space by one implementing the YAML 1.1
    line-break set, so a file carrying one has no single meaning.
    """
    text = f"a{chr(point)}b"
    value = {"n": text}

    encoded = wrench.YAML.encode(value)
    assert encoded == f'"n": "a{in_yaml}b"\n'.encode()
    assert wrench.TOML.encode(value) == f'n = "a{in_toml}b"\n'.encode()

    # Reading it back is the half that was broken: two packs wrote files their
    # own parser then refused.
    assert wrench.YAML.decode(encoded)["n"] == text


# COVERS: FR-2.11 | property
def test_every_failure_is_wrenchs_own_type_with_its_step():
    """Six kinds on three axes, and the cause kept.

    `schema` against `validate` is the pair most easily lost: a schema that will
    not compile is not a document that does not match one, and the fix is to a
    different file.
    """
    strict = wrench.compile_schema(
        "strict.json",
        '{"$schema":"https://json-schema.org/draft/2020-12/schema", "type":"object","required":["a"]}',
    )

    def failing(call):
        with pytest.raises(wrench.Error) as caught:
            call()
        return caught.value

    cases = {
        "schema": lambda: wrench.compile_schema("bad.json", '{"type": 42}'),
        "validate": lambda: strict.validate({}),
        "parse": lambda: wrench.YAML.decode(b"a: [1,\n"),
        "encode": lambda: wrench.YAML.encode({"a": object()}),
        "read": lambda: wrench.load_yaml_file("f.yaml", ANYTHING, Stub(error=OSError("nope"))),
        "write": lambda: wrench.save_yaml_file({"a": 1}, "f.yaml", ANYTHING, Stub(error=OSError("nope"))),
    }
    for want, call in cases.items():
        assert failing(call).step == want
