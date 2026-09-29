"""Tests for `bin/test-schema-validity.py`, the gate's check that every validator agrees.

They live here for the reasons `test_suite_parity.py` sets out at the top of
that file: `testdata/` is the one directory both `test-suite-parity.py` and
`test-traceability.py` ignore, and a checker's own tests discharge no
requirement in wrench's contract.

Nothing here builds a pack or asks a real validator. The readers are short
stand-ins written to `tmp_path`, because what needs checking is that the checker
fails when a reader disagrees, goes quiet, or stops checking. A run against the
real readers answers a different question and answers it green.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

CHECKER = Path(__file__).resolve().parents[2] / "bin" / "test-schema-validity.py"
CONTROLS = Path(__file__).resolve().parents[1] / "schema-validity" / "controls"

# Judges the way a real validator would on the two controls: a numeric `type`
# and a string `required` are invalid, and anything else passes.
HONEST = """
import json, sys
for path in sys.argv[1:]:
    doc = json.load(open(path))
    name = path.rsplit("/", 1)[-1]
    bad = isinstance(doc.get("type"), int) or isinstance(doc.get("required"), str)
    print(("INVALID " + name + ": bad") if bad else ("ok " + name))
"""

# A reader that stopped checking and says yes to everything.
ACCEPTS_ALL = """
import sys
for path in sys.argv[1:]:
    print("ok " + path.rsplit("/", 1)[-1])
"""

# A reader that refuses one shipped schema.
REFUSES_ENVELOPE = HONEST.replace(
    "bad = ", 'bad = name.startswith("envelope") or '
)

# A reader that says nothing about one file it was handed.
SILENT_ON_ONE = HONEST.replace("print(", 'name.startswith("jig") or print(')


def _schemas(tmp_path: Path) -> Path:
    shipped = tmp_path / "schemas"
    shipped.mkdir()
    for name in ("envelope", "jig"):
        document = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"https://example.invalid/{name}.schema.json",
            "type": "object",
        }
        (shipped / f"{name}.schema.json").write_text(json.dumps(document), encoding="utf-8")
    return shipped


def _reader(tmp_path: Path, name: str, body: str) -> str:
    path = tmp_path / f"{name}.py"
    path.write_text(body, encoding="utf-8")
    return f"{name}={sys.executable} {path}"


def _run(tmp_path: Path, *, bound: tuple[str, ...], independent: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    argv = [
        sys.executable,
        str(CHECKER),
        "--schemas",
        str(_schemas(tmp_path)),
        "--controls",
        str(CONTROLS),
        "--work",
        str(tmp_path / "work"),
        "--reader",
        "none-of-the-real-ones",
    ]
    for reader in bound:
        argv += ["--extra-reader", reader]
    for reader in independent:
        argv += ["--independent-reader", reader]
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def test_readers_that_agree_pass(tmp_path: Path) -> None:
    done = _run(
        tmp_path,
        bound=(_reader(tmp_path, "one", HONEST), _reader(tmp_path, "two", HONEST)),
        independent=(_reader(tmp_path, "outsider", HONEST),),
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "PASS: 3 readers agree on 2 schemas and refuse 2 controls" in done.stdout


def test_a_reader_accepting_a_control_fails(tmp_path: Path) -> None:
    done = _run(
        tmp_path,
        bound=(_reader(tmp_path, "lax", ACCEPTS_ALL),),
        independent=(_reader(tmp_path, "outsider", HONEST),),
    )
    assert done.returncode == 1, done.stdout + done.stderr
    assert "lax accepted the control type-is-a-number.schema.json" in done.stdout


def test_a_reader_refusing_a_shipped_schema_fails(tmp_path: Path) -> None:
    done = _run(
        tmp_path,
        bound=(_reader(tmp_path, "strict", REFUSES_ENVELOPE),),
        independent=(_reader(tmp_path, "outsider", HONEST),),
    )
    assert done.returncode == 1, done.stdout + done.stderr
    assert "strict refused the shipped envelope.schema.json" in done.stdout


def test_without_an_independent_reader_it_is_not_a_pass(tmp_path: Path) -> None:
    done = _run(
        tmp_path,
        bound=(_reader(tmp_path, "one", HONEST), _reader(tmp_path, "two", HONEST)),
        independent=(),
    )
    assert done.returncode == 2, done.stdout + done.stderr
    assert "no reader independent of the packs took part" in done.stdout


def test_a_reader_silent_on_a_file_is_not_a_pass(tmp_path: Path) -> None:
    done = _run(
        tmp_path,
        bound=(_reader(tmp_path, "quiet", SILENT_ON_ONE),),
        independent=(_reader(tmp_path, "outsider", HONEST),),
    )
    assert done.returncode == 2, done.stdout + done.stderr
    assert "quiet: said nothing about jig.schema.json" in done.stdout


def test_a_reader_that_cannot_run_is_not_a_pass(tmp_path: Path) -> None:
    done = _run(
        tmp_path,
        bound=("missing=/does/not/exist",),
        independent=(_reader(tmp_path, "outsider", HONEST),),
    )
    assert done.returncode == 2, done.stdout + done.stderr
    assert "could not be run" in done.stdout
