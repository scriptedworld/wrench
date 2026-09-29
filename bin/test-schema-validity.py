#!/usr/bin/env python3
"""Fail unless every validator wrench binds, and one it does not, agree the schemas are valid.

`docs/DECISIONS/the-gate-asks-every-validator-and-requires-agreement.md` is the
rule: the gate asks every validator a pack binds whether each shipped schema is
valid 2020-12, requires them all to say yes, and asks at least one
implementation no pack binds, so the verdict cannot become agreement among
wrench's own bindings alone.

Each reader is also handed two controls under `testdata/schema-validity/controls/`,
schemas that are not valid 2020-12, and must refuse both. A reader that stopped
checking would otherwise say yes to everything and read as agreement.

A shipped schema is copied with its `$id` moved to `probe.invalid` before a pack
sees it, because every pack refuses to compile a caller's schema that redefines
a shipped `$id`. The body is otherwise byte for byte the shipped one.

    0   every reader ran, accepted every shipped schema and refused every control
    1   a reader refused a shipped schema or accepted a control
    2   a reader could not be built or run, said nothing about a file it was
        handed, or no reader independent of the packs took part

Exit 2 dominates, so "nothing ran" can never read as a pass.

## The driver protocol

A driver takes file paths and prints one line per file, `ok NAME` or
`INVALID NAME: reason`. The line is the verdict and the exit status is not read,
because a driver's status says whether it ran and not what it found.

## Adding a reader

One entry in `default_readers` and a driver under
`testdata/schema-validity/<name>/`. `--extra-reader NAME=COMMAND` runs one before
it is added, and `--independent-reader` does the same for one no pack binds.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DRIVERS = REPO / "testdata" / "schema-validity"
PROBE_HOST = "https://probe.invalid/"
SUMMARY = "Fail unless every validator wrench binds, and one it does not, agree the schemas are valid."


@dataclass(frozen=True)
class Reader:
    """A validator, the driver that asks it, and what has to happen first."""

    name: str
    driver: list[str]
    independent: bool = False
    build: list[str] = field(default_factory=list)
    cwd: Path = REPO
    env: dict[str, str] = field(default_factory=dict)


def default_readers(work: Path) -> list[Reader]:
    """Every validator a pack binds, and the one no pack binds."""
    return [
        Reader(
            name="go",
            build=["go", "build", "-o", str(work / "go-driver"), "."],
            driver=[str(work / "go-driver")],
            cwd=DRIVERS / "go",
        ),
        Reader(
            name="python",
            driver=[sys.executable, str(DRIVERS / "python" / "driver.py")],
            env={"PYTHONPATH": str(REPO / "python")},
        ),
        Reader(
            name="rust",
            build=[
                "cargo",
                "build",
                "--quiet",
                "--manifest-path",
                str(DRIVERS / "rust" / "Cargo.toml"),
            ],
            driver=[str(work / "rust-target" / "debug" / "wrench-schema-validity-driver")],
            env={"CARGO_TARGET_DIR": str(work / "rust-target")},
        ),
        Reader(
            name="typescript",
            driver=["node", str(DRIVERS / "typescript" / "driver.ts")],
        ),
        Reader(
            name="hyperjump",
            driver=["deno", "run", "--allow-read", str(DRIVERS / "hyperjump" / "driver.ts")],
            independent=True,
        ),
    ]


def run(argv: list[str], cwd: Path, env: dict[str, str], timeout: int) -> subprocess.CompletedProcess[str]:
    """Run a command, reporting what went wrong instead of raising it.

    A driver that is not there raises, and a traceback here would exit with a
    status that reads as a verdict. A reader that did not run has to reach the
    report as a reader that did not run.
    """
    merged = dict(os.environ)
    merged.update(env)
    try:
        return subprocess.run(argv, cwd=str(cwd), env=merged, capture_output=True,
                              text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        why = f"it did not finish inside {timeout}s"
    except OSError as unrunnable:
        why = str(unrunnable)
    return subprocess.CompletedProcess(argv, 127, "", f"{argv[0]}: {why}")


def tail(done: subprocess.CompletedProcess[str], lines: int = 8) -> str:
    text = (done.stderr or "") + (done.stdout or "")
    return "\n".join([line for line in text.splitlines() if line.strip()][-lines:])


def probes(schemas: Path, work: Path) -> list[Path]:
    """The shipped schemas, each under a probe `$id` and otherwise unchanged."""
    out = work / "probes"
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for source in sorted(schemas.glob("*.schema.json")):
        document = json.loads(source.read_text(encoding="utf-8"))
        document["$id"] = PROBE_HOST + source.name
        target = out / source.name
        target.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        written.append(target)
    return written


def verdicts(stdout: str) -> dict[str, str]:
    """Each file's verdict, keyed by name, from the driver's own lines."""
    found = {}
    for line in stdout.splitlines():
        word, _, rest = line.partition(" ")
        name, _, _ = rest.partition(":")
        if word in ("ok", "INVALID") and name:
            found[name.strip()] = word
    return found


@dataclass
class Report:
    """What each reader said about each file, and what could not be run."""

    said: dict[str, dict[str, str]] = field(default_factory=dict)
    unrunnable: list[str] = field(default_factory=list)
    wrong: list[str] = field(default_factory=list)


def check(readers: list[Reader], shipped: list[Path], controls: list[Path],
          timeout: int) -> Report:
    report = Report()
    files = [*shipped, *controls]
    for reader in readers:
        if reader.build:
            built = run(reader.build, reader.cwd, reader.env, timeout)
            if built.returncode != 0:
                report.unrunnable.append(f"{reader.name}: the driver did not build\n{tail(built)}")
                continue
        done = run([*reader.driver, *map(str, files)], reader.cwd, reader.env, timeout)
        said = verdicts(done.stdout)
        silent = [f.name for f in files if f.name not in said]
        if silent:
            report.unrunnable.append(
                f"{reader.name}: said nothing about {', '.join(silent)}\n{tail(done)}"
            )
            continue
        report.said[reader.name] = said
        for path in shipped:
            if said[path.name] != "ok":
                report.wrong.append(f"{reader.name} refused the shipped {path.name}")
        for path in controls:
            if said[path.name] != "INVALID":
                report.wrong.append(f"{reader.name} accepted the control {path.name}")
    return report


def show(report: Report, readers: list[Reader], files: list[Path]) -> None:
    ran = [r for r in readers if r.name in report.said]
    width = max([len(f.name) for f in files] + [4])
    print(" " * width + "".join(f"{r.name:>12}" for r in ran))
    for path in files:
        row = "".join(f"{report.said[r.name][path.name]:>12}" for r in ran)
        print(f"{path.name:>{width}}{row}")
    independent = [r.name for r in ran if r.independent]
    print(f"\nindependent of every pack: {', '.join(independent) or 'none'}")
    if report.wrong:
        print("\ndisagreements")
        for line in report.wrong:
            print(f"  {line}")
    if report.unrunnable:
        print("\ncould not be run")
        for line in report.unrunnable:
            print(f"  {line}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=SUMMARY)
    parser.add_argument("--schemas", type=Path, default=REPO / "schemas")
    parser.add_argument("--controls", type=Path, default=DRIVERS / "controls")
    parser.add_argument("--work", type=Path, default=REPO / ".ephemera" / "schema-validity",
                        help="where the drivers are built and the probes are written")
    parser.add_argument("--reader", action="append", default=[],
                        help="run only this reader from the table, repeatable")
    parser.add_argument("--extra-reader", action="append", default=[], metavar="NAME=COMMAND",
                        help="a driver not in the table, bound by a pack")
    parser.add_argument("--independent-reader", action="append", default=[],
                        metavar="NAME=COMMAND", help="a driver not in the table, bound by no pack")
    parser.add_argument("--timeout", type=int, default=600)
    return parser.parse_args(argv)


def assemble(args: argparse.Namespace, work: Path) -> list[Reader]:
    readers = default_readers(work)
    if args.reader:
        readers = [r for r in readers if r.name in args.reader]
    for entry, independent in [(e, False) for e in args.extra_reader] + [
        (e, True) for e in args.independent_reader
    ]:
        name, _, command = entry.partition("=")
        readers.append(Reader(name=name, driver=command.split(), independent=independent))
    return readers


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    readers = assemble(args, work)
    shipped = probes(args.schemas, work)
    controls = sorted(args.controls.glob("*.schema.json"))
    if not readers or not shipped or not controls:
        print("no readers, no shipped schemas or no controls, so this asserts nothing")
        return 2

    report = check(readers, shipped, controls, args.timeout)
    show(report, readers, [*shipped, *controls])

    if report.unrunnable:
        print(f"\nFAIL: {len(report.unrunnable)} reader(s) could not be run")
        return 2
    if not any(r.independent for r in readers if r.name in report.said):
        print("\nFAIL: no reader independent of the packs took part")
        return 2
    if report.wrong:
        print(f"\nFAIL: {len(report.wrong)} verdict(s) wrong")
        return 1
    print(f"\nPASS: {len(report.said)} readers agree on {len(shipped)} schemas "
          f"and refuse {len(controls)} controls")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
