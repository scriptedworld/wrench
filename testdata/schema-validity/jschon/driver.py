"""Ask jschon whether each file is a valid 2020-12 schema.

    driver.py FILE...

One line per file, `ok NAME` or `INVALID NAME: reason`, wrench's driver
protocol. Each file is evaluated as an instance of the 2020-12 meta-schema
jschon's catalogue bundles; no source is added, so a reference outside the
bundled set cannot be loaded.
"""

import sys
from pathlib import Path

from jschon import JSON, URI, create_catalog

META = URI("https://json-schema.org/draft/2020-12/schema")


def main(paths: list[str]) -> int:
    catalog = create_catalog("2020-12")
    meta = catalog.get_schema(META)
    refused = 0
    for path in paths:
        name = Path(path).name
        result = meta.evaluate(JSON.loadf(path))
        if result.valid:
            print(f"ok {name}")
            continue
        refused += 1
        print(f"INVALID {name}: not valid against the 2020-12 meta-schema")
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
