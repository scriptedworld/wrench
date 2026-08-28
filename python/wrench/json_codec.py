"""The JSON codec: bytes to a structure, and a structure to canonical bytes.

Canonical form is two-space indent, one key to a line, and keys sorted. JSON
needs no quoting rule because it has one spelling per type already, which is
what makes it the cheaper of the two formats wrench ships.

Sorted for the same reason YAML is: a mapping has no order of its own, so
sorting is what makes two runs over the same structure produce the same bytes.

THE FORM IS `deno fmt` CLEAN, and that is deliberate rather than incidental.
`bolt.wrench-quality.yaml` already runs `deno fmt --check` over `schemas/*.json`,
so a second answer about JSON layout would put two formatters in one repository.
Measured 2026-08-28: sorted, two-space, one-key-per-line JSON passes `deno fmt`
unchanged.

`deno fmt` does NOT sort keys and collapses a short object onto one line, so it
is a formatter rather than a canonical form. Matching it is one direction only:
what wrench emits, deno accepts.
"""

from __future__ import annotations

import json

INDENT = 2


class JSONCodec:
    """The format, knowing nothing about where the bytes came from."""

    def decode(self, data: bytes) -> object:
        """Bytes into maps, lists and scalars."""
        return json.loads(data)

    def encode(self, value: object) -> bytes:
        """A structure into canonical bytes.

        `sort_keys` is the canonical half. `allow_nan=False` refuses NaN and the
        infinities, which JSON cannot spell and which the YAML codec refuses for
        the same reason: a file no consumer in this ecosystem can validate.
        """
        try:
            text = json.dumps(
                value,
                indent=INDENT,
                sort_keys=True,
                allow_nan=False,
                ensure_ascii=False,
            )
        except ValueError as err:
            raise ValueError(f"cannot write in canonical form: {err}") from err
        except TypeError as err:
            raise ValueError(f"cannot write in canonical form: {err}") from err
        return (text + "\n").encode("utf-8")


JSON = JSONCodec()
