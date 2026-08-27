#!/usr/bin/env python3
"""Fail when one contract's suites do not cover the same requirements.

A repository with a library per language states one contract and implements it
more than once. Each suite passing says nothing about whether they exercise the
same rows, so a row held by one suite alone is a row every other pack can break
silently, and every suite stays green while it happens.

This reads the `COVERS:` marks out of each declared suite and compares the sets.

WHY IT CANNOT BE A PER-BASE TASK. The comparison is between bases by definition.
A checker run once inside `go/` and once inside `python/` sees one suite each
time and can only report that it covers what it covers. This has to stand where
it can see all of them at once.

THIS IS WRENCH-SPECIFIC. It is not a common-quality checker and does not belong
in toolbox: it compares suites against each other, which only a repository with a
library per language has to do. wrench is about to have four such directories.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# `# COVERS: FR-1.1, FR-2.3 | positive` in Python, `// COVERS: ...` in Go, and
# whatever a third language spells a comment as. The marker is the anchor, not
# the comment syntax, so a new language needs no change here.
#
# THE KIND IS PART OF THE COMPARISON. Two suites both citing FR-3.1 says they
# both touched it, not that they test the same thing: one asserting the positive
# path and the other the negative one is a divergence that an id-only comparison
# calls level. Measured in wrench, that hid three of them.
COVERS = re.compile(r"COVERS:\s*([^|\n]+)\|\s*(\w+)")

# `| FR-6.1 | ... | [A] |` and the optional scope naming the suites expected to
# discharge it, inside the SAME bracket: `| FR-6.1 | ... | [A python] |`.
#
# One bracket, and no `|` inside it. toolbox's test-traceability.py takes a row's
# marker to be its last bracketed cell and matches `^\[[^\]]*\]$`, so a second
# bracket reads as no marker at all and a `|` splits the cell in two. Both were
# tried and both broke that checker quietly, which is the argument for the
# spelling being awkward rather than pretty.
ROW = re.compile(r"^\|\s*(FR-[0-9A-Za-z.]+)\s*\|(.*)\|\s*(\[[^|\]]*\])\s*\|\s*$")
SCOPE = re.compile(r"\b([a-z][a-z0-9_-]*)\b")

# A row under this heading has been retired and is not expected to be covered.
RETIRED = re.compile(r"^##\s+Retired\s*$", re.MULTILINE)


def covered_by(paths: list[Path]) -> set[tuple[str, str]]:
    """Every (requirement, kind) pair cited by a COVERS mark in these files."""
    found: set[tuple[str, str]] = set()
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for ids, kind in COVERS.findall(text):
            for part in ids.split(","):
                if part.strip():
                    found.add((part.strip(), kind.strip()))
    return found


def declared(requirements: Path) -> tuple[set[str], dict[str, set[str]]]:
    """The live requirement ids, and for each one the suites expected to cover
    it. A row naming no scope is expected in every suite.

    Everything below the `## Retired` heading is excluded, because a retired id
    is not expected to be covered anywhere and citing one is the traceability
    checker's business rather than this one's.
    """
    text = requirements.read_text(encoding="utf-8")
    split = RETIRED.search(text)
    live = text[: split.start()] if split else text

    ids: set[str] = set()
    scopes: dict[str, set[str]] = {}
    for line in live.splitlines():
        matched = ROW.match(line)
        if not matched:
            continue
        identifier, _, markers = matched.groups()
        if "[?]" in markers:  # open, carries no test by design
            continue
        ids.add(identifier)
        # SCOPE only matches a lowercase bracketed word, so the provenance
        # markers [A], [D], [A/D] and [?] cannot be mistaken for a suite name.
        named = set(SCOPE.findall(markers))
        if named:
            scopes[identifier] = named
    return ids, scopes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", required=True, type=Path)
    parser.add_argument(
        "--suite",
        action="append",
        required=True,
        metavar="NAME=GLOB",
        help="a named suite and the glob its test files match, repeatable",
    )
    parser.add_argument("root", nargs="?", default=".", type=Path)
    args = parser.parse_args()

    suites: dict[str, set[str]] = {}
    for spec in args.suite:
        if "=" not in spec:
            print(f"parity: --suite wants NAME=GLOB, got {spec!r}", file=sys.stderr)
            return 2
        name, glob = spec.split("=", 1)
        files = sorted(args.root.glob(glob))
        if not files:
            print(f"parity: suite {name!r} matched no files at {glob!r}", file=sys.stderr)
            return 2
        suites[name] = covered_by(files)

    if len(suites) < 2:
        print("parity: two or more suites are needed to compare", file=sys.stderr)
        return 2

    ids, scopes = declared(args.requirements)
    failures: list[str] = []

    for name, unknown in sorted(
        (n, sorted(u)) for n, u in ((n, scopes.get(n, set()) - set(suites)) for n in ids) if u
    ):
        failures.append(
            f"{name} is scoped to {', '.join(unknown)}, which is not a declared suite"
        )

    # Every (requirement, kind) any suite claims, compared against every suite
    # expected to hold it. A pair one suite has and another does not is a test
    # written once for a contract implemented more than once.
    every = {pair for covered in suites.values() for pair in covered}
    for identifier, kind in sorted(every):
        if identifier not in ids:
            continue  # retired or unknown: the traceability checker's business
        expected = scopes.get(identifier, set(suites))
        if expected - set(suites):
            continue  # already reported above
        missing = sorted(n for n in expected if (identifier, kind) not in suites[n])
        if missing and len(missing) < len(expected):
            holding = sorted(n for n in expected if (identifier, kind) in suites[n])
            failures.append(
                f"{identifier} | {kind} is in {', '.join(holding)} "
                f"but not in {', '.join(missing)}"
            )

    # A row cited by a suite it is not scoped to is the declaration being wrong
    # rather than a test being missing, and it is worth saying differently.
    for name, covered in sorted(suites.items()):
        for identifier, _ in sorted(covered):
            expected = scopes.get(identifier)
            if identifier in ids and expected and name not in expected:
                failures.append(
                    f"{identifier} is cited by {name} but scoped to "
                    f"{', '.join(sorted(expected))}"
                )

    for line in dict.fromkeys(failures):
        print(f"parity: {line}")

    if failures:
        print(f"\n{len(set(failures))} divergence(s) between the suites.")
        return 1

    scoped = sum(1 for i in ids if i in scopes)
    print(
        f"{len(every)} test(s) held level across "
        f"{len(suites)} suites: {', '.join(sorted(suites))}."
    )
    if scoped:
        print(f"{scoped} requirement(s) scoped to a subset, declared in {args.requirements}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
