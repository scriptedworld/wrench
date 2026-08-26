"""Tests for the Python pack.

The canonical cases come from `testdata/canonical/`, the same directories the
Go pack is held to. That is the point of them: two implementations agreeing on
the schema and disagreeing on the bytes is the failure a shared fixture set
exists to catch, and neither pack is the oracle for the other.
"""

from __future__ import annotations

import subprocess
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
        self.data = data
        self.error = error
        self.saw_path: str | None = None
        self.written: bytes | None = None

    def read(self, path: str) -> bytes:
        self.saw_path = path
        if self.error:
            raise self.error
        return self.data

    def write(self, path: str, data: bytes) -> None:
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


# COVERS: FR-4.1, FR-4.2, FR-4.3, FR-4.4, FR-5.5, FR-5.6 | property
@pytest.mark.parametrize("case", CASES)
def test_canonical_form_matches_the_shared_fixtures(case):
    """The bytes this pack emits are the bytes the fixture declares. The Go
    pack is held to the same file."""
    directory = FIXTURES / case
    value = wrench.YAML.decode((directory / "input.yaml").read_bytes())
    assert wrench.YAML.encode(value).decode() == (directory / "canonical.yaml").read_text()


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
def test_nan_and_the_infinities_are_refused():
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            wrench.YAML.encode([value])


# ---- the two calls ----------------------------------------------------------


# COVERS: FR-2.1, FR-2.2 | positive
def test_load_returns_the_validated_structure():
    value = wrench.load_formatted_file(
        "output.yaml", wrench.ENVELOPE_SCHEMA, wrench.YAML, Stub(VALID_ENVELOPE)
    )
    assert value == {"success": True}


# COVERS: FR-2.5a | positive
def test_the_reader_is_handed_the_path():
    reader = Stub(VALID_ENVELOPE)
    wrench.load_formatted_file("nowhere/output.yaml", wrench.ENVELOPE_SCHEMA, wrench.YAML, reader)
    assert reader.saw_path == "nowhere/output.yaml"


# COVERS: FR-2.3 | negative
def test_a_call_with_no_schema_is_refused():
    with pytest.raises(ValueError, match="no schema"):
        wrench.load_formatted_file("f.yaml", None, wrench.YAML, Stub())
    with pytest.raises(ValueError, match="no schema"):
        wrench.save_formatted_file({}, "f.yaml", None, wrench.YAML, Stub())


# COVERS: FR-2.2 | negative
def test_a_call_with_no_codec_or_no_io_is_refused():
    with pytest.raises(ValueError, match="no codec"):
        wrench.load_formatted_file("f.yaml", ANYTHING, None, Stub())
    with pytest.raises(ValueError, match="no reader"):
        wrench.load_formatted_file("f.yaml", ANYTHING, wrench.YAML, None)
    with pytest.raises(ValueError, match="no writer"):
        wrench.save_formatted_file({}, "f.yaml", ANYTHING, wrench.YAML, None)


# COVERS: FR-2.6 | negative
def test_a_failure_says_which_step_failed():
    with pytest.raises(wrench.ReadError):
        wrench.load_formatted_file(
            "gone.yaml", wrench.ENVELOPE_SCHEMA, wrench.YAML, Stub(error=FileNotFoundError())
        )

    with pytest.raises(wrench.ParseError):
        wrench.load_formatted_file(
            "f.yaml", wrench.ENVELOPE_SCHEMA, wrench.YAML, Stub(b"success: [unterminated\n")
        )

    with pytest.raises(wrench.ValidationError):
        wrench.load_formatted_file(
            "f.yaml", wrench.ENVELOPE_SCHEMA, wrench.YAML, Stub(b'success: "yes"\n')
        )


# COVERS: FR-2.4 | negative
def test_save_refuses_a_structure_it_would_not_read_back():
    writer = Stub()
    with pytest.raises(wrench.ValidationError):
        wrench.save_formatted_file(
            {"success": "yes"}, "f.yaml", wrench.ENVELOPE_SCHEMA, wrench.YAML, writer
        )
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


# COVERS: FR-3.1, FR-3.2, FR-3.5 | positive
def test_all_three_shipped_schemas_load_from_the_one_copy():
    for schema in (wrench.ENVELOPE_SCHEMA, wrench.JIG_SCHEMA, wrench.MANIFEST_SCHEMA):
        schema.validate.__self__  # noqa: B018 - it is a Schema, not a function
    wrench.ENVELOPE_SCHEMA.validate({"success": True})
    wrench.JIG_SCHEMA.validate({"tasks": [{"name": "build", "command": "go build ./..."}]})
    wrench.MANIFEST_SCHEMA.validate(
        {
            "task": "build",
            "ordinal": 0,
            "command": "go build ./...",
            "variables": {
                "project_root": "/p",
                "base_dir": "/p",
                "work_dir": "/p/w",
                "config_dir": "/p",
                "output_dir": "/p/o",
            },
        }
    )


# COVERS: FR-3.2 | regression
def test_a_validation_error_names_the_schema_by_id_not_by_local_path():
    """The identifier lands in the error, the error lands in a reason, and a
    reason travels as evidence."""
    with pytest.raises(wrench.ValidationError) as caught:
        wrench.load_formatted_file(
            "f.yaml", wrench.ENVELOPE_SCHEMA, wrench.YAML, Stub(b'success: "yes"\n')
        )
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
    back = wrench.load_formatted_file(
        path, wrench.ENVELOPE_SCHEMA, wrench.YAML, wrench.LOCAL_FILE
    )

    assert back == value
    assert back["metadata"]["statistics"]["checked"] == 12


# COVERS: FR-6.3 | positive
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
    result = subprocess.run(
        [sys.executable, "-c", "import wrench; print(wrench.YAML)"],
        cwd=str(ROOT),
        env={"PYTHONPATH": str(ROOT / "python"), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
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
