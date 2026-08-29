#!/usr/bin/env python3
"""No suppression pragma anywhere in this repository that SUPPRESSIONS misses.

Hard rule 4: a pragma needs a person to have answered why before it is written,
and it is then registered.

**This exists because `common-quality` runs at each pack's own base.** Pointed at
`python/`, it reads eleven files, so `bin/`, the Go pack and the Rust pack are
unchecked by construction and a pragma written in any of them is silent. This
runs the same checker over the whole tree, which is forty-six.

That is not hypothetical. Two `nosec` pragmas were once written into `bin/` by
reflex and nothing objected; removing them, the replacement comment wrapped so
the spelling landed at the start of a comment line, and the register read the
prose as a bare pragma silencing the file. Neither was noticed by any check.

**It runs toolbox's register rather than reimplementing it.** A first attempt did
reimplement it and was wrong within minutes: the pattern matched the word inside
prose, and it reported the register's own docstring. The real one already reads
every language and only counts a pragma where one would take effect.

Exits 0 when every pragma is registered and 1 when one is not, so it needs no
adapter and runs as a pre-commit hook as readily as a gate task.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Run the shared register over the whole repository."""
    root = Path(__file__).resolve().parent.parent
    register = root / "SUPPRESSIONS"
    checker = root / "bin" / "suppression-register.py"

    if not register.is_file():
        print(f"no register at {register}")
        return 1

    # The register is passed as it is tracked. It used to be rewritten into a
    # second frame first, because the checker keyed paths relative to whatever
    # base it was scanning, so one register could not satisfy a pack-based run
    # and a root run at once. Since toolbox bed07d2 both sides resolve against
    # the repository, and the translation would double the prefix.
    run = subprocess.run(
        [sys.executable, str(checker), "--register", str(register), str(root)],
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
