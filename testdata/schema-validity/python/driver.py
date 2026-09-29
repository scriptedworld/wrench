#!/usr/bin/env python3
"""Ask the Python pack whether each file is a valid schema.

    driver.py FILE...

One line per file, `ok NAME` or `INVALID NAME: reason`, which is what
bin/test-schema-validity.py reads. The exit status is not what it reads.
"""

import sys
from pathlib import Path

import wrench


def main() -> int:
    refused = 0
    for arg in sys.argv[1:]:
        path = Path(arg)
        try:
            wrench.compile_schema(path.name, path.read_text(encoding="utf-8"))
        except wrench.Error as err:
            refused += 1
            print(f"INVALID {path.name}: {str(err).splitlines()[0]}")
            continue
        print(f"ok {path.name}")
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
