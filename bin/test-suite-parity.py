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

# A scope clause is `suites` or `suites:kinds`, both comma-separated:
#
#     [A/D python]                  every kind of FR-6.1 is python's alone
#     [A go,python:edge,negative]   only those two kinds are, and the rest of
#                                   the row is expected everywhere
#
# THE KIND HALF IS NOT DECORATION. A requirement can be discharged by every pack
# for one kind and by a subset for another, and wrench has one: FR-4.1's property
# case is covered by all three packs, while its edge and negative cases test
# refusing a value the Rust type system cannot construct. Scoping the whole row
# would stop the checker noticing if Rust ever dropped the property test, and
# would report the row it does hold as wrongly cited.
#
# Still one bracket and still no `|`, because toolbox's test-traceability.py
# takes a row's marker to be its last bracketed cell and matches `^\[[^\]]*\]$`.
SCOPE = re.compile(
    r"([a-z][a-z0-9_-]*(?:,[a-z][a-z0-9_-]*)*)(?::([a-z][a-z0-9_-]*(?:,[a-z][a-z0-9_-]*)*))?"
)

# A row under a `## Retired` heading has been retired and is not expected to be
# covered. Every `##` heading resets that state, so a section following a retired
# one is live again.
#
# THESE TWO SPELLINGS MATCH toolbox's test-traceability.py EXACTLY, and that is
# the point rather than a coincidence. Both checkers read the same document and
# an id live for one and retired for the other is the same class of defect this
# repository exists to catch, one tier up.
#
# It was measured, not anticipated. This checker used to split the text at the
# first `## Retired` and treat everything after it as retired, which disagreed
# with the traceability checker for any row under a LATER heading. Reproduce with
# a file holding `## Retired`, a row, then `## Live again` and a second row cited
# by one suite and not another:
#
#     parity        second row retired, skipped, "held level",  EXIT 0
#     traceability  second row live, uncovered,                 EXIT 1
#
# The dangerous half is that this checker was the one reporting the pass, on a
# divergence it exists to find. It was latent in wrench only because
# `## Retired` was the last section of a single REQUIREMENTS.md, which is no
# longer how this repository stores its contract: `docs/REQUIREMENTS/` is one
# file per requirement and retirement is carried by a `.retired` name. The
# heading still has to be read correctly for every adopter that has not split.
#
# NOTHING TESTS THIS FILE, which is how that survived. See
# `clank/tasks/wrench/gate/40-the-checkers-have-no-tests`.
HEADING = re.compile(r"^##\s+(?P<title>.+?)\s*$")
RETIRED_HEADING = re.compile(r"^retired\b", re.IGNORECASE)


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


def is_retired_by_name(path: Path) -> bool:
    """A document whose name retires everything in it.

    Retirement carried by the filename has no heading, no switch and no
    below-this-line, so the row that retires something and the row appended
    after it cannot be confused. It is also visible in `ls` without opening
    anything, and it leaves a retired requirement in the group it always sat in.

    Both spellings count, matching toolbox's checker: `.retired` is the shape a
    split repository uses and `.retired.md` stays readable to anything expecting
    markdown.
    """
    return path.name.endswith((".retired", ".retired.md"))


def requirement_documents(path: Path) -> list[Path]:
    """The documents a `--requirements` path names: one file, or a tree of them.

    A directory holds one file per requirement,
    `<level>/<group>/FR-<id>-<slug>.md`, nested as deep as the grouping wants.
    Every `.md` beneath is read, README included, so a requirement written
    somewhere unexpected fails loudly for having no test rather than being
    skipped for sitting in the wrong file.

    `.retired` is read as well as `.md`. A retired document this checker cannot
    see is the quiet way to lose the never-reuse guarantee.

    Sorted, so a repeated id names the same two files whatever order the
    filesystem hands them back in.
    """
    if path.is_dir():
        found = (p for pattern in ("*.md", "*.retired") for p in path.rglob(pattern))
        return sorted({p for p in found if p.is_file()})
    return [path]


def declared(
    requirements: Path,
) -> tuple[set[str], dict[str, set[str]], dict[tuple[str, str], set[str]]]:
    """The live requirement ids, the suites expected to cover each whole row, and
    the suites expected to cover a single (requirement, kind) pair.

    A row naming no scope is expected in every suite, and a pair with its own
    scope overrides whatever the row says.

    A retired id is excluded, because it is not expected to be covered anywhere
    and citing one is the traceability checker's business rather than this one's.
    Retirement comes from the document's name or from a `## Retired` heading
    above the row, read exactly as `test-traceability.py` reads them.
    """
    ids: set[str] = set()
    scopes: dict[str, set[str]] = {}
    kind_scopes: dict[tuple[str, str], set[str]] = {}

    for document in requirement_documents(requirements):
        in_retired = is_retired_by_name(document)
        for line in document.read_text(encoding="utf-8").splitlines():
            heading = HEADING.match(line)
            if heading:
                # A named document stays retired whatever its headings say, so a
                # `## Retired` inside one cannot un-retire the rest of it.
                if not is_retired_by_name(document):
                    in_retired = bool(RETIRED_HEADING.match(heading.group("title")))
                continue

            matched = ROW.match(line)
            if not matched or in_retired:
                continue
            identifier, _, markers = matched.groups()
            if "[?]" in markers:  # open, carries no test by design
                continue
            ids.add(identifier)
            # SCOPE only matches lowercase words, so the provenance markers [A],
            # [D], [A/D] and [?] cannot be mistaken for a suite name.
            for named, kinds in SCOPE.findall(markers):
                suites = {part for part in named.split(",") if part}
                if not suites:
                    continue
                if kinds:
                    for kind in kinds.split(","):
                        if kind:
                            kind_scopes[(identifier, kind)] = suites
                else:
                    scopes[identifier] = suites
    return ids, scopes, kind_scopes


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

    suites: dict[str, set[tuple[str, str]]] = {}
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

    ids, scopes, kind_scopes = declared(args.requirements)

    # REFUSING TO PASS ON NOTHING. Every cited pair whose id is not live is
    # skipped as the traceability checker's business, so an empty set of ids
    # skips everything and reports the suites level. That is a green produced by
    # finding no contract at all, which is what a mistyped path or a directory
    # this checker cannot read looks like.
    if not ids:
        print(
            f"parity: {args.requirements} declares no live requirements; "
            "refusing to pass vacuously",
            file=sys.stderr,
        )
        return 2

    failures: list[str] = []

    def declared_scope(identifier: str, kind: str) -> set[str] | None:
        """The suites a pair is scoped to, or None when nothing scopes it.

        The pair wins over the row, so a row scoped to one set can still name a
        different set for a single kind.
        """
        if (identifier, kind) in kind_scopes:
            return kind_scopes[(identifier, kind)]
        return scopes.get(identifier)

    named_scopes: list[tuple[str, set[str]]] = [(i, s) for i, s in scopes.items()]
    named_scopes += [(f"{i} | {k}", s) for (i, k), s in kind_scopes.items()]
    for name, unknown in sorted(
        (n, sorted(u)) for n, u in ((n, s - set(suites)) for n, s in named_scopes) if u
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
        expected = declared_scope(identifier, kind) or set(suites)
        if expected - set(suites):
            continue  # already reported above
        missing = sorted(n for n in expected if (identifier, kind) not in suites[n])
        if missing and len(missing) < len(expected):
            holding = sorted(n for n in expected if (identifier, kind) in suites[n])
            failures.append(
                f"{identifier} | {kind} is in {', '.join(holding)} "
                f"but not in {', '.join(missing)}"
            )

    # A pair cited by a suite it is not scoped to is the declaration being wrong
    # rather than a test being missing, and it is worth saying differently.
    for name, covered in sorted(suites.items()):
        for identifier, kind in sorted(covered):
            expected = declared_scope(identifier, kind)
            if identifier in ids and expected and name not in expected:
                failures.append(
                    f"{identifier} | {kind} is cited by {name} but scoped to "
                    f"{', '.join(sorted(expected))}"
                )

    for line in dict.fromkeys(failures):
        print(f"parity: {line}")

    if failures:
        print(f"\n{len(set(failures))} divergence(s) between the suites.")
        return 1

    scoped = sum(1 for i in ids if i in scopes)
    scoped_pairs = sum(1 for i, _ in kind_scopes if i in ids)
    print(
        f"{len(every)} test(s) held level across "
        f"{len(suites)} suites: {', '.join(sorted(suites))}."
    )
    if scoped:
        print(f"{scoped} requirement(s) scoped to a subset, declared in {args.requirements}.")
    if scoped_pairs:
        print(
            f"{scoped_pairs} requirement/kind pair(s) scoped to a subset, "
            f"declared in {args.requirements}."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
