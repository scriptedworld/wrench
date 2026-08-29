"""Tests for `bin/generate-shipped.py`, which compiles the schemas into the Go
and Python packs.

The generated files are committed, so `--check` is the only thing standing
between them and the drift FR-3.2 exists to prevent. A check that passes
vacuously would leave that copy unwatched while reporting that it is watched,
so each test below breaks the tree in one way and asserts the check notices.

`testdata/` is where these sit for the reason `test_suite_parity.py` sets out at
length: it is the one directory both of wrench's own checkers ignore.

The script resolves its root as the parent of its own directory, so a temporary
`bin/` and `schemas/` beside each other is a complete tree to run it in, and no
test here touches the real one.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "bin" / "generate-shipped.py"

ONE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://example.invalid/one.schema.json",
    "type": "object",
}


def tree(tmp_path: Path, schemas: Mapping[str, object]) -> Path:
    """A throwaway repository holding the script and the schemas given."""
    (tmp_path / "bin").mkdir()
    shutil.copy(SCRIPT, tmp_path / "bin" / SCRIPT.name)
    (tmp_path / "schemas").mkdir()
    (tmp_path / "python" / "wrench").mkdir(parents=True)
    for name, document in schemas.items():
        (tmp_path / "schemas" / name).write_text(json.dumps(document, indent=2) + "\n")
    return tmp_path


def run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(root / "bin" / SCRIPT.name), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_fresh_run_writes_both_packs(tmp_path):
    root = tree(tmp_path, {"one.schema.json": ONE_SCHEMA})

    assert run(root).returncode == 0

    go = (root / "shipped_gen.go").read_text()
    python = (root / "python" / "wrench" / "_shipped.py").read_text()
    assert "one.schema.json" in go
    assert "one.schema.json" in python
    assert "https://example.invalid/one.schema.json" in go
    assert "https://example.invalid/one.schema.json" in python


def test_check_passes_immediately_after_a_run(tmp_path):
    root = tree(tmp_path, {"one.schema.json": ONE_SCHEMA})
    run(root)

    done = run(root, "--check")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "1 schema(s)" in done.stdout


def test_check_catches_an_edited_schema(tmp_path):
    """The case the gate exists for: a schema changes and nobody regenerates."""
    root = tree(tmp_path, {"one.schema.json": ONE_SCHEMA})
    run(root)

    edited = dict(ONE_SCHEMA, description="added after generating")
    (root / "schemas" / "one.schema.json").write_text(json.dumps(edited, indent=2) + "\n")

    done = run(root, "--check")
    assert done.returncode == 1
    assert "STALE  shipped_gen.go" in done.stdout
    assert "STALE  python/wrench/_shipped.py" in done.stdout


def test_check_catches_a_hand_edited_generated_file(tmp_path):
    """The other direction: the schema is untouched and the copy was edited."""
    root = tree(tmp_path, {"one.schema.json": ONE_SCHEMA})
    run(root)

    generated = root / "python" / "wrench" / "_shipped.py"
    generated.write_text(generated.read_text().replace("object", "array"))

    done = run(root, "--check")
    assert done.returncode == 1
    assert "STALE  python/wrench/_shipped.py" in done.stdout
    assert "STALE  shipped_gen.go" not in done.stdout, "only the edited file is stale"


def test_check_catches_an_added_schema(tmp_path):
    root = tree(tmp_path, {"one.schema.json": ONE_SCHEMA})
    run(root)

    second = dict(ONE_SCHEMA, **{"$id": "https://example.invalid/two.schema.json"})
    (root / "schemas" / "two.schema.json").write_text(json.dumps(second, indent=2) + "\n")

    assert run(root, "--check").returncode == 1


def test_check_catches_a_removed_schema(tmp_path):
    root = tree(tmp_path, {"one.schema.json": ONE_SCHEMA, "two.schema.json": dict(ONE_SCHEMA, **{"$id": "https://example.invalid/two.schema.json"})})
    run(root)

    (root / "schemas" / "two.schema.json").unlink()

    assert run(root, "--check").returncode == 1


def test_a_schema_with_no_id_is_refused(tmp_path):
    """FR-3.6 names a schema by its $id, so one without it can be referenced by
    nothing and must not reach a pack."""
    root = tree(tmp_path, {"one.schema.json": {"type": "object"}})

    done = run(root)
    assert done.returncode != 0
    assert "declares no $id" in done.stderr + done.stdout


def test_an_empty_directory_is_refused(tmp_path):
    """A generator that happily writes nothing would let every pack ship no
    schemas while the gate reported success."""
    root = tree(tmp_path, {})

    done = run(root)
    assert done.returncode != 0
    assert "no schemas" in done.stderr + done.stdout


def test_the_generated_order_does_not_depend_on_the_directory_read(tmp_path):
    """Two runs must produce the same bytes, or --check fails on nothing."""
    schemas = {
        "b.schema.json": dict(ONE_SCHEMA, **{"$id": "https://example.invalid/b.schema.json"}),
        "a.schema.json": dict(ONE_SCHEMA, **{"$id": "https://example.invalid/a.schema.json"}),
    }
    root = tree(tmp_path, schemas)

    run(root)
    first = (root / "shipped_gen.go").read_text()
    run(root)
    assert (root / "shipped_gen.go").read_text() == first
    assert first.index("a.schema.json") < first.index("b.schema.json")
