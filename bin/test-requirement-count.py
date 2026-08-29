#!/usr/bin/env python3
"""Every live requirement file reaches the traceability checker's denominator.

A row the checker cannot parse is not reported missing: it is simply absent, and
the run reports a clean pass over a contract with a hole in it. Measured in
wrench 2026-08-29, adding a well-formed file with a two-letter suffix
`FR-4.9aa` left the output at `41 of 41` and exit 0, identical to not adding it.
`clank/inbox/toolbox/a-two-letter-requirement-suffix-is-silently-uncounted`
carries that, and asks for a loud refusal in the checker itself.

**This check closes the same class locally and does not depend on the grammar.**
It compares two counts of the same set reached two different ways:

    files on disk  ==  the checker's denominator + what it exempted

so whatever the next unparseable id turns out to be, the arithmetic notices. The
idea is the bolt session's, who reconciled 247 against 244 + 3 in their own tree
after losing a gate reading to exactly this.

Exits 0 when they agree and 1 when they do not, so it needs no adapter.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# The checker's own summary is the only place its denominator is stated. Reading
# a number out of it is fine; reading a VERDICT out of it would not be, which is
# why the exit code is checked separately below.
COUNTED = re.compile(r"\((\d+) of (\d+)\)")
EXEMPT = re.compile(r"(\d+) open and exempt")


def main() -> int:
    """Compare the files on disk against what the checker managed to read."""
    root = Path(__file__).resolve().parent.parent
    requirements = root / "docs" / "REQUIREMENTS"

    # `.retired` in the name retires a requirement, and a retired row is not
    # held to coverage, so only the live ones are counted.
    live = sorted(p for p in requirements.rglob("FR-*.md") if ".retired" not in p.name)

    checker = root / "bin" / "test-traceability.py"
    # No pragma here. bandit runs at base python/ and does not scan bin/, so one
    # would suppress nothing while going unregistered in SUPPRESSIONS, which is
    # the shape hard rule 4 exists to prevent. If the scan ever widens, the
    # finding surfaces for a person to answer rather than being pre-empted.
    #
    # KEEP THE SPELLING OFF THE START OF A COMMENT LINE. The register reads a
    # line opening with the pragma as a bare one silencing everything, and it
    # cannot tell prose from a directive. Caught here 2026-08-29 by the hook.
    run = subprocess.run(
        [sys.executable, str(checker), "--requirements", str(requirements), str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if run.returncode != 0:
        print("traceability itself failed, so its counts say nothing:")
        print(run.stdout.strip())
        return 1

    counted = COUNTED.search(run.stdout)
    if not counted:
        print(f"could not find a count in the checker's output:\n{run.stdout}")
        return 1
    denominator = int(counted.group(2))
    exempt = int(match.group(1)) if (match := EXEMPT.search(run.stdout)) else 0

    if len(live) == denominator + exempt:
        print(f"every requirement file reaches the checker ({len(live)} live = {denominator} + {exempt} exempt)")
        return 0

    print(
        f"{len(live)} live requirement files, but the checker saw {denominator} "
        f"and exempted {exempt}, which is {denominator + exempt}."
    )
    print("A file it cannot parse is absent rather than reported, so look for an id it refuses:")
    for path in live:
        print(f"  {path.relative_to(root)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
