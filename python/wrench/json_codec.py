"""The JSON codec: bytes to a structure, and a structure to canonical bytes.

Canonical form is two-space indent, one key to a line, and keys sorted. JSON
needs no quoting rule because it already has one spelling per type, which is
what makes it the cheaper of the formats wrench ships.

Keys are sorted for the reason the YAML codec sorts them: a mapping has no order
of its own, so sorting is what makes two runs over the same structure produce
the same bytes.

The form is `deno fmt` clean, and that is deliberate. `bolt.wrench-quality.yaml`
already runs `deno fmt --check` over `schemas/*.json`, so a second answer about
JSON layout would put two formatters in one repository.

**The structure is walked by hand, and only because of floats.** `json.dumps`
was correct about everything else and offers no supported hook for how a number
is spelled: with `indent` set the pure-Python encoder runs, and it formats every
float with `float.__repr__` taken as a default argument, which a subclass cannot
override and which no parameter reaches. `repr` chooses an exponent on a
threshold of its own, so it disagrees with this pack's YAML and TOML codecs and
with the other two packs. FR-4.8 states one spelling and
`docs/DECISIONS/a-codec-emits-by-hand-when-libraries-disagree.md` says what to
do when a library will not write it: emit by hand.

String escaping still goes through `json.dumps`, which is the part of the
library that is right, so this walk owns layout and numbers and nothing else.
"""

from __future__ import annotations

import json

from wrench.codec import _bare_scalar, _normalise
from wrench.errors import EncodeError, ParseError, wrapping

INDENT = 2


class JSONCodec:
    """The format, knowing nothing about where the bytes came from."""

    def decode(self, data: bytes) -> object:
        """Bytes into maps, lists and scalars.

        `json.JSONDecodeError` does not cross this boundary; the cause is kept.

        `_normalise` is shared with the YAML and TOML codecs rather than
        reimplemented, so an integer past int64 widens to a float here on the
        same terms. json.loads produces Python's unbounded int, which is the one
        type no other pack has.
        """
        with wrapping(ParseError):
            return _normalise(json.loads(data))

    def encode(self, value: object) -> bytes:
        """A structure into canonical bytes."""
        with wrapping(EncodeError):
            return (_value(value, 0) + "\n").encode("utf-8")


def _value(value: object, depth: int) -> str:
    """One value, laid out from `depth` levels of indent."""
    if isinstance(value, dict):
        return _mapping(value, depth)
    if isinstance(value, list):
        return _sequence(value, depth)
    return _scalar(value)


def _mapping(value: dict[object, object], depth: int) -> str:
    """A mapping, keys sorted, one to a line."""
    if not value:
        return "{}"
    pad = " " * (INDENT * (depth + 1))
    rows = [f"{pad}{_string(_key(key))}: {_value(value[key], depth + 1)}" for key in sorted(value, key=_key)]
    return "{\n" + ",\n".join(rows) + "\n" + " " * (INDENT * depth) + "}"


def _sequence(value: list[object], depth: int) -> str:
    """A sequence, one entry to a line."""
    if not value:
        return "[]"
    pad = " " * (INDENT * (depth + 1))
    rows = [f"{pad}{_value(entry, depth + 1)}" for entry in value]
    return "[\n" + ",\n".join(rows) + "\n" + " " * (INDENT * depth) + "]"


def _key(key: object) -> str:
    """A mapping key, which JSON can only spell as a string."""
    if not isinstance(key, str):
        raise ValueError(f"cannot write a {type(key).__name__} key in canonical form")
    return key


def _scalar(value: object) -> str:
    """One scalar, spelled so its type survives being read back."""
    bare = _bare_scalar(value)
    if bare is not None:
        return bare
    if isinstance(value, str):
        return _string(value)
    raise ValueError(f"cannot write {type(value).__name__} in canonical form")


def _string(value: str) -> str:
    """A quoted string, escaped the way JSON spells escapes.

    `ensure_ascii=False` keeps a non-ASCII character as itself, which is what
    the other two packs write and what `deno fmt` leaves alone.
    """
    return json.dumps(value, ensure_ascii=False)


JSON = JSONCodec()
