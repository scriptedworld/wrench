#!/usr/bin/env python3
"""Fail when one pack's output does not decode to the same value in another.

FR-5.5 is the claim: any pack's output must decode to the same value in every
other pack. Packs agree on structure and not on bytes, so a difference in
indentation, quoting or line width is not a failure and a string coming back as
a number is. `docs/DECISIONS/packs-agree-on-structure-not-on-bytes.md` carries
the argument and `docs/SPEC.md` states the value model being compared.

Every pack encodes `testdata/parity-tree.json` to YAML and to JSON, then every
pack decodes every file, including its own. The value that comes back is
compared against the tree by structure and by type, key by key. The full matrix
is printed whether or not it passes, because a matrix with a hole in it is the
finding a green line would hide.

    0   every writer, reader and format agreed
    1   at least one divergence
    2   a pack could not be built or run, or fewer than two packs took part

Exit 2 dominates, so "no packs ran" can never read as a pass.

## The wire, and why it is not JSON

The comparison needs one representation every driver can write and this checker
can read. JSON is the obvious candidate and it is the wrong one twice over: it
cannot tell an integer from a float that happens to be whole, which is one of
the divergences being hunted, and a reader taking every number as a double
silently rounds 9223372036854775807 to 9223372036854775808, which is another.
Writing the probe as JSON would launder exactly the faults it is here to catch.

So the wire is JSON carrying a tagged form in which **every scalar is a string**
and its type is an explicit tag. Nothing about the value is left to a JSON
parser's number handling:

    {"k": "null"}
    {"k": "bool",  "v": "true"}
    {"k": "int",   "v": "-9223372036854775808"}   exact decimal, any width
    {"k": "float", "v": "bff0000000000000"}       IEEE-754 bits, big-endian
    {"k": "str",   "v": "636166c3a9"}             the UTF-8 bytes, in hex
    {"k": "seq",   "v": [node, ...]}
    {"k": "map",   "v": [[<key as UTF-8 hex>, node], ...]}
    {"k": "foreign", "v": "<type name>: <repr>"}  outside FR-2.9's model

An integer and a whole float are different tags, so they cannot be confused. A
float is carried as its 64 bits, so no decimal-to-binary rounding happens on the
wire at all and -0.0 stays distinct from 0.0. A string is carried as its bytes,
so no encoder's escaping, no normalisation and no replacement of an unpaired
surrogate can touch it. The envelope is written with each language's stock JSON
library rather than with the pack under test, which is safe precisely because
every scalar in it is a string.

`foreign` is how a driver reports a value outside wrench's model, a Go
`time.Time` from a YAML timestamp being the case FR-2.9 names. The driver passes
it through under that tag instead of coercing it, so the divergence is reported
against the key it happened at rather than being repaired in the driver.

## Adding a pack

One entry in `default_packs`, holding the command that builds the driver and the
command that runs it, plus a driver under `testdata/parity/<language>/` speaking
the two subcommands above. Nothing else here knows a pack's name, and
`--extra-pack NAME=COMMAND` runs one before it is added.
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

WIRE = 1
FORMATS = ("yaml", "json")

REPO = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Pack:
    """A pack, its driver, and what has to happen before the driver runs."""

    name: str
    driver: list[str]
    build: list[str] = field(default_factory=list)
    cwd: Path = REPO
    env: dict[str, str] = field(default_factory=dict)


def default_packs(work: Path) -> list[Pack]:
    """The packs that take part, one entry each.

    The C++ pack has no codec yet, so it has nothing to encode with and cannot
    take part. The TypeScript pack is mid-port and its files are moving. Both
    are absent rather than stubbed: a stub that reported agreement would be the
    only thing here that could lie.
    """
    parity = REPO / "testdata" / "parity"
    return [
        Pack(
            name="go",
            build=["go", "build", "-o", str(work / "go-driver"), "."],
            driver=[str(work / "go-driver")],
            cwd=parity / "go",
        ),
        Pack(
            name="python",
            driver=[sys.executable, str(parity / "python" / "driver.py")],
            env={"PYTHONPATH": str(REPO / "python")},
        ),
        Pack(
            name="rust",
            build=[
                "cargo",
                "build",
                "--quiet",
                "--manifest-path",
                str(parity / "rust" / "Cargo.toml"),
            ],
            driver=[str(work / "rust-target" / "debug" / "wrench-parity-driver")],
            env={"CARGO_TARGET_DIR": str(work / "rust-target")},
        ),
    ]


# The tree, as the tagged wire form. json.load is the authority on which
# literals are integers and which are floats, and Python's int is unbounded, so
# the expectation is exact at both int64 boundaries.


def to_wire(value: Any) -> dict[str, Any]:
    if value is None:
        return {"k": "null"}
    if isinstance(value, bool):
        return {"k": "bool", "v": "true" if value else "false"}
    if isinstance(value, int):
        return {"k": "int", "v": str(value)}
    if isinstance(value, float):
        return {"k": "float", "v": struct.pack(">d", value).hex()}
    if isinstance(value, str):
        return {"k": "str", "v": value.encode("utf-8").hex()}
    if isinstance(value, list):
        return {"k": "seq", "v": [to_wire(item) for item in value]}
    if isinstance(value, dict):
        return {
            "k": "map",
            "v": [[k.encode("utf-8").hex(), to_wire(v)] for k, v in value.items()],
        }
    raise ValueError(f"{type(value).__name__} is outside wrench's value model")


def describe(node: dict[str, Any]) -> str:
    """One readable line for a wire node, for the divergence report."""
    kind = node["k"]
    if kind == "null":
        return "null"
    if kind == "int":
        return f"int {node['v']}"
    if kind == "float":
        bits = bytes.fromhex(node["v"])
        return f"float {struct.unpack('>d', bits)[0]!r} (bits {node['v']})"
    if kind == "str":
        return f"string {bytes.fromhex(node['v']).decode('utf-8', 'replace')!r}"
    if kind == "bool":
        return f"bool {node['v']}"
    if kind == "seq":
        return f"sequence of {len(node['v'])}"
    if kind == "map":
        return f"map of {len(node['v'])}"
    if kind == "foreign":
        return f"outside the value model: {node['v']}"
    return f"unknown wire kind {kind!r}"


def unhex(key: str) -> str:
    return bytes.fromhex(key).decode("utf-8", "replace")


def diverge(expected: Any, actual: Any, path: str = "") -> list[str]:
    """Every place the two wire trees differ, deepest key named.

    A map is compared as a mapping and not as a list, because a mapping has no
    order of its own. Key order is canonical form's business (FR-4.3), which is
    a property of the bytes and not of the value.
    """
    at = path or "(root)"
    if expected["k"] != actual["k"]:
        return [f"{at}: expected {describe(expected)}, got {describe(actual)}"]
    if expected["k"] == "seq":
        return _diverge_seq(expected, actual, path, at)
    if expected["k"] == "map":
        return _diverge_map(expected, actual, path, at)
    if expected.get("v") != actual.get("v"):
        return [f"{at}: expected {describe(expected)}, got {describe(actual)}"]
    return []


def _diverge_seq(expected: Any, actual: Any, path: str, at: str) -> list[str]:
    if len(expected["v"]) != len(actual["v"]):
        return [f"{at}: expected {len(expected['v'])} items, got {len(actual['v'])}"]
    found: list[str] = []
    for index, (want, got) in enumerate(zip(expected["v"], actual["v"])):
        found += diverge(want, got, f"{path}[{index}]")
    return found


def _diverge_map(expected: Any, actual: Any, path: str, at: str) -> list[str]:
    want = dict(expected["v"])
    got = dict(actual["v"])
    found = [f"{at}: key {unhex(k)!r} is missing" for k in want if k not in got]
    found += [
        f"{at}: key {unhex(k)!r} was not in the tree" for k in got if k not in want
    ]
    for key, item in want.items():
        if key in got:
            found += diverge(item, got[key], f"{path}.{unhex(key)}")
    return found


@dataclass
class Run:
    """What one driver invocation did, read from its artifact and not its code."""

    ok: bool
    detail: str = ""
    probe: dict[str, Any] | None = None


class Driver:
    """Runs one pack's driver and reads what it produced."""

    def __init__(self, pack: Pack, work: Path, timeout: int) -> None:
        self.pack = pack
        self.work = work
        self.timeout = timeout

    def _run(self, argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        """Run a command, reporting what went wrong rather than raising it.

        A driver binary that is not there raises rather than returning a
        status, and an exception here would leave the process with a traceback
        and an exit code that reads as a divergence. A pack that did not run
        has to reach the report as a pack that did not run.
        """
        env = dict(os.environ)
        env.update(self.pack.env)
        try:
            return subprocess.run(
                argv,
                cwd=str(cwd),
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            why = f"it did not finish inside {self.timeout}s"
        except OSError as unrunnable:
            why = str(unrunnable)
        return subprocess.CompletedProcess(argv, 127, "", f"{argv[0]}: {why}")

    def build(self) -> Run:
        if not self.pack.build:
            return Run(True, "nothing to build")
        done = self._run(self.pack.build, self.pack.cwd)
        if done.returncode != 0:
            return Run(False, tail(done))
        target = Path(self.pack.driver[0])
        if not target.exists():
            return Run(False, f"the build reported success and {target} is not there")
        return Run(True, str(target))

    def encode(self, fmt: str, probe: Path, out: Path) -> Run:
        out.unlink(missing_ok=True)
        done = self._run(
            [*self.pack.driver, "encode", fmt, str(probe), str(out)], self.pack.cwd
        )
        if not out.exists() or out.stat().st_size == 0:
            return Run(False, tail(done) or f"{out} was not written")
        if done.returncode != 0:
            return Run(False, tail(done))
        return Run(True, f"{out.stat().st_size} bytes")

    def decode(self, fmt: str, source: Path, probe: Path) -> Run:
        probe.unlink(missing_ok=True)
        done = self._run(
            [*self.pack.driver, "decode", fmt, str(source), str(probe)], self.pack.cwd
        )
        if not probe.exists():
            return Run(False, tail(done) or f"{probe} was not written")
        try:
            wire = json.loads(probe.read_text(encoding="utf-8"))
        except (OSError, ValueError) as unreadable:
            return Run(False, f"the probe it wrote does not parse: {unreadable}")
        if wire.get("wire") != WIRE:
            return Run(False, f"probe wire version {wire.get('wire')} is not {WIRE}")
        if done.returncode != 0:
            return Run(False, tail(done))
        return Run(True, "", wire["value"])


def tail(done: subprocess.CompletedProcess[str], lines: int = 12) -> str:
    text = (done.stderr or "") + (done.stdout or "")
    kept = [line for line in text.splitlines() if line.strip()][-lines:]
    return "\n".join(kept)


@dataclass
class Report:
    """The matrix, the divergences, and anything that could not be run."""

    cells: dict[tuple[str, str, str], list[str]] = field(default_factory=dict)
    unrunnable: list[str] = field(default_factory=list)
    packs: list[str] = field(default_factory=list)


def check(packs: list[Pack], tree: Any, work: Path, timeout: int) -> Report:
    report = Report()
    drivers: dict[str, Driver] = {}
    for pack in packs:
        driver = Driver(pack, work, timeout)
        built = driver.build()
        if not built.ok:
            report.unrunnable.append(
                f"{pack.name}: the driver did not build\n{built.detail}"
            )
            continue
        drivers[pack.name] = driver
    report.packs = list(drivers)

    probe = work / "tree.wire.json"
    expected = {"wire": WIRE, "value": to_wire(tree)}
    probe.write_text(json.dumps(expected), encoding="utf-8")

    written: dict[tuple[str, str], Path] = {}
    for name, driver in drivers.items():
        for fmt in FORMATS:
            out = work / f"{name}.{fmt}"
            done = driver.encode(fmt, probe, out)
            if not done.ok:
                report.unrunnable.append(
                    f"{name}: encoding {fmt} failed\n{done.detail}"
                )
                continue
            written[(name, fmt)] = out

    for (writer, fmt), path in sorted(written.items()):
        for reader, driver in drivers.items():
            out = work / f"read-{writer}-{fmt}-by-{reader}.json"
            done = driver.decode(fmt, path, out)
            if not done.ok:
                report.cells[(writer, reader, fmt)] = [
                    f"the read failed: {done.detail}"
                ]
                continue
            report.cells[(writer, reader, fmt)] = diverge(expected["value"], done.probe)
    note_dead_readers(report)
    return report


def note_dead_readers(report: Report) -> None:
    """A pack that read nothing at all is an unrunnable pack, not a divergence.

    One failed read is a finding about parity: a pack that cannot take a
    sibling's file is FR-5.5 failing, and it belongs in the matrix. A pack that
    failed every read it was given is a pack that did not run, and calling that
    a divergence would let a driver that never starts be reported as a result.
    """
    for reader in report.packs:
        mine = [found for key, found in report.cells.items() if key[1] == reader]
        if mine and all(
            found and found[0].startswith("the read failed") for found in mine
        ):
            report.unrunnable.append(f"{reader}: every read failed, so it did not run")


def show(report: Report, tree_path: Path) -> None:
    print(f"tree: {tree_path}")
    print(f"packs: {', '.join(report.packs) if report.packs else 'none'}")
    for fmt in FORMATS:
        readers = [r for r in report.packs if any(k[1] == r for k in report.cells)]
        writers = sorted({k[0] for k in report.cells if k[2] == fmt})
        if not writers:
            continue
        print(f"\n{fmt}: writer down the side, reader across the top")
        print("    " + "".join(f"{r:>10}" for r in readers))
        for writer in writers:
            row = ""
            for reader in readers:
                found = report.cells.get((writer, reader, fmt))
                if found is None:
                    row += f"{'-':>10}"
                else:
                    row += f"{'pass' if not found else f'FAIL {len(found)}':>10}"
            print(f"{writer:>4}" + row)

    divergences = {key: found for key, found in sorted(report.cells.items()) if found}
    if divergences:
        print("\ndivergences")
        for (writer, reader, fmt), found in divergences.items():
            print(f"\n  {writer} wrote {fmt}, {reader} read it: {len(found)}")
            for line in found:
                print(f"    {line}")

    if report.unrunnable:
        print("\ncould not be run")
        for line in report.unrunnable:
            print(f"  {line}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--tree", type=Path, default=REPO / "testdata" / "parity-tree.json"
    )
    parser.add_argument(
        "--work",
        type=Path,
        default=REPO / ".ephemera" / "parity",
        help="where the drivers, the encoded files and the probes are put",
    )
    parser.add_argument(
        "--pack",
        action="append",
        default=[],
        help="run only this pack, repeatable",
    )
    parser.add_argument(
        "--extra-pack",
        action="append",
        default=[],
        metavar="NAME=COMMAND",
        help=(
            "a driver not in the table, to try a pack out before adding it, "
            "and to prove this checker fails when a pack diverges"
        ),
    )
    parser.add_argument("--timeout", type=int, default=600)
    return parser.parse_args(argv)


def assemble(args: argparse.Namespace, work: Path) -> list[Pack]:
    packs = default_packs(work)
    if args.pack:
        packs = [p for p in packs if p.name in args.pack]
    for entry in args.extra_pack:
        name, _, command = entry.partition("=")
        packs.append(Pack(name=name, driver=command.split()))
    return packs


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    tree = json.loads(args.tree.read_text(encoding="utf-8"))

    packs = assemble(args, work)
    if not packs:
        print("no packs selected", file=sys.stderr)
        return 2

    report = check(packs, tree, work, args.timeout)
    show(report, args.tree)

    if report.unrunnable:
        print(f"\nFAIL: {len(report.unrunnable)} pack(s) could not be run")
        return 2
    if len(report.packs) < 2:
        print(f"\nFAIL: {len(report.packs)} pack(s) ran, and parity needs two")
        return 2
    failures = sum(1 for found in report.cells.values() if found)
    if failures:
        print(
            f"\nFAIL: {failures} of {len(report.cells)} writer/reader/format pairs diverged"
        )
        return 1
    print(f"\nPASS: {len(report.cells)} writer/reader/format pairs agree")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
