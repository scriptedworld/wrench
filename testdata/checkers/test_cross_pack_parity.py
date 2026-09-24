"""Tests for `bin/test-cross-pack-parity.py`, wrench's cross-pack parity check.

They live here for the reasons `test_suite_parity.py` sets out at the top of
that file: `testdata/` is the one directory both `test-suite-parity.py` and
`test-traceability.py` ignore, and a checker's own tests discharge no
requirement in wrench's contract.

Nothing here builds or runs a pack. The drivers are two-line stand-ins written
to `tmp_path`, because what needs checking is that the checker reports a
divergence and exits on it. A run against the real packs answers a different
question and answers it green, which is the state a checker is worth nothing in.
"""

from __future__ import annotations

import importlib.util
import json
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any

CHECKER = Path(__file__).resolve().parents[2] / "bin" / "test-cross-pack-parity.py"


def _checker_module() -> Any:
    """The checker as a module, its filename carrying a dash."""
    spec = importlib.util.spec_from_file_location("cross_pack_parity", CHECKER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Registered before it runs, because @dataclass resolves an annotation
    # through sys.modules and raises on a module that is not in it yet.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


parity = _checker_module()


# A driver that agrees: encode copies the wire form to the output file and
# decode copies it back, so the value that comes out is the value that went in.
FAITHFUL = """
import json, sys
action, fmt, source, target = sys.argv[1:]
open(target, "w").write(open(source).read())
"""

# A driver that changes one value on the way out, the integer becoming a float.
# That is the divergence FR-5.5 is about, and the one a JSON interchange could
# not have carried.
DIVERGENT = """
import json, struct, sys
action, fmt, source, target = sys.argv[1:]
wire = json.load(open(source))
for key, node in wire["value"]["v"]:
    if bytes.fromhex(key).decode() == "count":
        node.clear()
        node.update({"k": "float", "v": struct.pack(">d", 7.0).hex()})
json.dump(wire, open(target, "w"))
"""


def _driver(tmp_path: Path, name: str, body: str) -> str:
    path = tmp_path / f"{name}.py"
    path.write_text(body, encoding="utf-8")
    return f"{name}={sys.executable} {path}"


def _tree(tmp_path: Path, value: dict[str, Any]) -> Path:
    path = tmp_path / "tree.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _run(tmp_path: Path, tree: Path, *packs: str) -> subprocess.CompletedProcess[str]:
    argv = [
        sys.executable,
        str(CHECKER),
        "--tree",
        str(tree),
        "--work",
        str(tmp_path / "work"),
        "--pack",
        "none-of-the-real-ones",
    ]
    for pack in packs:
        argv += ["--extra-pack", pack]
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def test_packs_that_agree_pass(tmp_path: Path) -> None:
    tree = _tree(tmp_path, {"count": 7, "name": "seven"})
    done = _run(
        tmp_path,
        tree,
        _driver(tmp_path, "one", FAITHFUL),
        _driver(tmp_path, "two", FAITHFUL),
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "PASS: 8 writer/reader/format pairs agree" in done.stdout


def test_a_divergent_pack_is_named_with_its_key(tmp_path: Path) -> None:
    tree = _tree(tmp_path, {"count": 7, "name": "seven"})
    done = _run(
        tmp_path,
        tree,
        _driver(tmp_path, "good", FAITHFUL),
        _driver(tmp_path, "bad", DIVERGENT),
    )
    assert done.returncode == 1, done.stdout + done.stderr
    assert "bad wrote yaml, good read it" in done.stdout
    assert ".count: expected int 7, got float 7.0" in done.stdout


def test_a_pack_that_cannot_run_is_not_a_pass(tmp_path: Path) -> None:
    tree = _tree(tmp_path, {"count": 7})
    done = _run(
        tmp_path,
        tree,
        _driver(tmp_path, "one", FAITHFUL),
        _driver(tmp_path, "two", FAITHFUL),
        "missing=/does/not/exist",
    )
    assert done.returncode == 2, done.stdout + done.stderr
    assert "could not be run" in done.stdout


def test_one_pack_alone_cannot_report_parity(tmp_path: Path) -> None:
    tree = _tree(tmp_path, {"count": 7})
    done = _run(tmp_path, tree, _driver(tmp_path, "only", FAITHFUL))
    assert done.returncode == 2, done.stdout + done.stderr
    assert "parity needs two" in done.stdout


def test_an_integer_and_a_whole_float_are_different_on_the_wire() -> None:
    """The distinction a JSON interchange would have lost."""
    assert parity.to_wire(1) == {"k": "int", "v": "1"}
    assert parity.to_wire(1.0)["k"] == "float"
    assert parity.diverge(parity.to_wire(1), parity.to_wire(1.0))


def test_negative_zero_keeps_its_sign_on_the_wire() -> None:
    """FR-4.11. Every decimal spelling of -0.0 reads back as 0.0 somewhere."""
    assert parity.to_wire(-0.0) != parity.to_wire(0.0)
    assert parity.diverge(parity.to_wire(-0.0), parity.to_wire(0.0))


def test_an_integer_past_a_double_is_carried_exactly() -> None:
    """9223372036854775807 as a double is 9223372036854775808."""
    assert parity.to_wire(2**63 - 1) == {"k": "int", "v": "9223372036854775807"}


def test_a_string_is_carried_as_its_bytes() -> None:
    """No escaping, no normalisation, and nothing an encoder can substitute."""
    assert parity.to_wire("café")["v"] == "636166c3a9"


def test_a_map_is_compared_as_a_mapping_and_not_as_a_list() -> None:
    """Key order is canonical form's business (FR-4.3), not the value's."""
    one = parity.to_wire({"a": 1, "b": 2})
    other = parity.to_wire({"b": 2, "a": 1})
    assert one != other
    assert not parity.diverge(one, other)


def test_a_missing_key_and_an_extra_one_are_both_reported() -> None:
    assert parity.diverge(parity.to_wire({"a": 1}), parity.to_wire({})) == [
        "(root): key 'a' is missing"
    ]
    assert parity.diverge(parity.to_wire({}), parity.to_wire({"a": 1})) == [
        "(root): key 'a' was not in the tree"
    ]


def test_a_float_that_lost_precision_is_reported_by_its_bits() -> None:
    nearly = struct.unpack(">d", struct.pack(">d", 0.1))[0]
    assert not parity.diverge(parity.to_wire(0.1), parity.to_wire(nearly))
    assert parity.diverge(parity.to_wire(0.1), parity.to_wire(0.1 + 2**-55))


def test_a_value_outside_the_model_is_reported_and_not_coerced() -> None:
    """A driver tags what its pack handed back, a Go time.Time being the case."""
    foreign = {"k": "foreign", "v": "time.Time: 2026-09-07"}
    found = parity.diverge(parity.to_wire("2026-09-07"), foreign)
    expected = (
        "(root): expected string '2026-09-07', "
        "got outside the value model: time.Time: 2026-09-07"
    )
    assert found == [expected]
