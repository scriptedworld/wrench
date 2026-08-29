#!/usr/bin/env python3
"""No suppression pragma anywhere in this repository that SUPPRESSIONS misses.

Hard rule 4: a pragma needs a person to have answered why before it is written,
and it is then registered. The register enforces that, and `common-quality` runs
it at base `python/` — so **`bin/`, the Go pack and the Rust pack are unchecked by
construction**, and a pragma written in any of them is silent.

That is not hypothetical. On 2026-08-29 this session wrote two `nosec` pragmas
into `bin/` by reflex and nothing objected. Removing them, the replacement
comment wrapped so the spelling landed at the start of a comment line, and the
register read the prose as a bare pragma silencing everything. Neither was
noticed by any check, because nothing scans `bin/`.

**This runs toolbox's register over the whole tree rather than reimplementing
it.** A first attempt did reimplement it and was wrong within minutes: the
pattern matched the word inside prose, and it reported the register's own
docstring. The real one already reads every language and only counts a pragma
where one would take effect.

**Why a generated view rather than changing SUPPRESSIONS.** `scan_source` keys
paths relative to the directory it is pointed at, so the register can be written
in exactly one frame. It is written in `python/`'s, because that is where
`common-quality` scans; a root scan needs the same rows spelled from the root.
Measured: root-relative rows make the `python/` run report both pragmas missing
AND both entries phantom. So the tracked file stays as `common-quality` needs it
and this generates the other frame, which is a workaround for
`clank/inbox/toolbox/a-shared-register-serves-two-bases` rather than a design.

Exits 0 when every pragma is registered and 1 when one is not, so it needs no
adapter and runs as a pre-commit hook as readily as a gate task.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# The base `common-quality` scans, whose frame the tracked register is written in.
SCANNED_BASE = "python/"


def main() -> int:
    """Run the real register at the root, against a root-relative view."""
    root = Path(__file__).resolve().parent.parent
    register = root / "SUPPRESSIONS"
    checker = root / "bin" / "suppression-register.py"

    if not register.is_file():
        print(f"no register at {register}")
        return 1

    # Only index rows carry a path; prose mentioning one is left alone, which is
    # why the rewrite is anchored to the four-space indent an index row uses.
    rewritten = "\n".join(
        f"    {SCANNED_BASE}{line.lstrip()}" if line.startswith("    ") and "/" in line else line
        for line in register.read_text().splitlines()
    )
    view = root / ".ephemera" / "SUPPRESSIONS.from-root"
    view.parent.mkdir(exist_ok=True)
    view.write_text(rewritten + "\n")

    run = subprocess.run(
        [sys.executable, str(checker), "--register", str(view), str(root)],
        capture_output=True,
        text=True,
        check=False,
        cwd=root,
    )
    sys.stdout.write(run.stdout)
    sys.stderr.write(run.stderr)
    if run.returncode != 0:
        print()
        print("Hard rule 4: ask a person, get an answer, record both in SUPPRESSIONS,")
        print("and only then write the pragma. Removing it is the other way through.")
    return run.returncode


if __name__ == "__main__":
    sys.exit(main())
