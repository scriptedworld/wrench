"""Tests for `bin/test-suite-parity.py`, wrench's own parity checker.

WHY THESE LIVE UNDER `testdata/` AND NOT BESIDE A SUITE. Two measured
constraints leave nowhere else, and both are worth knowing before anybody moves
them.

**A test of this checker cannot sit in a directory the checker reads.** The
checker greps `COVERS:` out of every file matching a suite glob, and these tests
must contain `COVERS:` marks as fixture data. Measured 2026-08-28: a file
placed in a python suite whose only mention of `FR-9.2` was a string inside a
test body turned a reported divergence into a pass.

    before   FR-9.2 | positive is in go but not in python   exit 1
    after    4 test(s) held level across 2 suites            exit 0

Nothing in that file tested FR-9.2 or claimed to. The string alone masked a real
divergence in the checker whose entire purpose is finding them.

**And it cannot sit anywhere `test-traceability.py` walks.** That checker
demands a `COVERS:` mark on every test function it finds, and these tests
discharge no requirement: wrench's contract is the schemas and the packs, and
this checker is wrench's own tooling. Citing a row here would be a false
citation to satisfy a checker. toolbox's equivalent tests cite toolbox
requirements honestly, because in toolbox the checkers are the product.

`testdata/` is in that checker's hardcoded `SKIP_DIRS` and is matched by no
suite glob, so it is the one directory both checkers ignore. **That is a hiding
place rather than a home**, and the gap is filed upstream as an open request.

Fixtures are written to `tmp_path` rather than committed, so no fixture file
exists on disk for either checker to walk into.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CHECKER = Path(__file__).resolve().parents[2] / "bin" / "test-suite-parity.py"

# One suite citing FR-9.2 and one not. Against a requirements set where FR-9.2 is
# live this is a divergence; against one where it is retired there is nothing to
# report. Every case below turns on which of those the checker decides.
GO_SUITE = "// COVERS: FR-9.1 | positive\n// COVERS: FR-9.2 | positive\n"
PYTHON_SUITE = "# COVERS: FR-9.1 | positive\n"


def run(root: Path, requirements: Path) -> subprocess.CompletedProcess[str]:
    """The checker as the gate runs it, over two suites in `root`."""
    return subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "--requirements",
            str(requirements),
            "--suite",
            "go=*_test.go",
            "--suite",
            "python=test_*.py",
            str(root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def suites(root: Path) -> None:
    """Write the two suites, one citing a row the other does not."""
    (root / "alpha_test.go").write_text(GO_SUITE)
    (root / "test_beta.py").write_text(PYTHON_SUITE)


def row(identifier: str, note: str) -> str:
    return f"| {identifier} | {note} | [A] |\n"


def test_a_row_after_a_later_heading_is_live(tmp_path):
    """A `## Retired` heading stops at the next heading, as it does for
    `test-traceability.py`.

    THE REGRESSION. This checker used to split its text at the first
    `## Retired` and treat the remainder of the file as gone, so this row was
    retired here and live there. Both readings are defensible; disagreeing is
    not, and this checker was the one reporting a pass on a real divergence.
    """
    suites(tmp_path)
    requirements = tmp_path / "reqs.md"
    requirements.write_text(
        "## Retired\n\n"
        + row("FR-9.1", "gone")
        + "\n## Live again\n\n"
        + row("FR-9.2", "here")
    )

    result = run(tmp_path, requirements)

    assert "FR-9.2 | positive is in go but not in python" in result.stdout
    assert result.returncode == 1


def test_a_row_under_the_retired_heading_is_not_expected_anywhere(tmp_path):
    """The heading still retires what sits directly under it."""
    suites(tmp_path)
    requirements = tmp_path / "reqs.md"
    requirements.write_text(
        row("FR-9.1", "live") + "\n## Retired\n\n" + row("FR-9.2", "gone")
    )

    result = run(tmp_path, requirements)

    assert "FR-9.2" not in result.stdout
    assert result.returncode == 0


def test_a_directory_of_requirements_is_read(tmp_path):
    """`--requirements` takes a tree, not only a file, which is what the split
    into one file per requirement needs."""
    suites(tmp_path)
    docs = tmp_path / "docs"
    (docs / "core").mkdir(parents=True)
    (docs / "core" / "FR-9.1-a.md").write_text(row("FR-9.1", "first file"))
    (docs / "core" / "FR-9.2-b.md").write_text(row("FR-9.2", "second file"))

    result = run(tmp_path, docs)

    assert "FR-9.2 | positive is in go but not in python" in result.stdout
    assert result.returncode == 1


def test_rows_in_separate_files_are_compared_against_each_other(tmp_path):
    """Two files, two rows, one verdict. A per-file comparison would report
    each row against itself and find nothing."""
    suites(tmp_path)
    docs = tmp_path / "docs"
    (docs / "core" / "deep").mkdir(parents=True)
    (docs / "core" / "FR-9.1-a.md").write_text(row("FR-9.1", "top level"))
    (docs / "core" / "deep" / "FR-9.2-b.md").write_text(row("FR-9.2", "two down"))

    result = run(tmp_path, docs)

    # FR-9.1 is level and FR-9.2 is not, so the nested file was read and its row
    # was compared against a suite declared in a different file entirely.
    assert "FR-9.2 | positive is in go but not in python" in result.stdout
    assert result.returncode == 1


def test_a_retired_filename_retires_its_rows_with_no_heading(tmp_path):
    """The NAME does it, and this file contains no `## Retired` anywhere.

    That control is the point. An earlier probe of this property put a
    `## Retired` heading inside the file and so could not tell the name from the
    heading, and reported whichever answer it went looking for.
    """
    suites(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "FR-9.1-a.md").write_text(row("FR-9.1", "live"))
    retired = docs / "FR-9.2-b.retired"
    retired.write_text(row("FR-9.2", "retired by this file's name alone"))

    assert "## Retired" not in retired.read_text()

    result = run(tmp_path, docs)

    assert "FR-9.2" not in result.stdout
    assert result.returncode == 0


def test_an_empty_requirements_directory_refuses(tmp_path):
    """A green produced by finding no contract at all is what a mistyped path
    looks like, so it exits rather than reporting the suites level."""
    suites(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()

    result = run(tmp_path, docs)

    assert "refusing to pass vacuously" in result.stderr
    assert result.returncode == 2


def test_a_suite_matching_no_files_refuses(tmp_path):
    """A stale suite glob is the divergence this checker exists to catch,
    hiding as a pass: no files means no citations means nothing to compare."""
    suites(tmp_path)
    requirements = tmp_path / "reqs.md"
    requirements.write_text(row("FR-9.1", "live"))

    result = subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "--requirements",
            str(requirements),
            "--suite",
            "go=*_test.go",
            "--suite",
            "rust=nothing/*.rs",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert "matched no files" in result.stderr
    assert result.returncode == 2
