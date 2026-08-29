"""The YAML codec: bytes to a structure, and a structure to canonical bytes.

Canonical form is block style, one key to a line, keys sorted, and a scalar
quoted exactly when it is meant to be a string. Booleans and numbers stay bare.

Quoting marks intent, so `no`, `1.20` and `null` survive a round trip as the
strings they were and a boolean stays a boolean. Keys are sorted because a
mapping has no order of its own, and sorting is what makes two runs over the
same structure produce the same bytes.

The emitter is written here rather than handed to PyYAML because PyYAML quotes
only what it must, which is the opposite rule: it decides by what would be
ambiguous rather than by what the value is.
"""

from __future__ import annotations

import datetime

import yaml

from wrench.errors import EncodeError, ParseError, wrapping
from wrench.float_text import canonical_float_text

INDENT = 2


class YAMLCodec:
    """The format, knowing nothing about where the bytes came from."""

    def decode(self, data: bytes) -> object:
        """Bytes into maps, lists and scalars.

        PyYAML's own exception types do not cross this boundary: a consumer
        should not have to know which YAML library wrench binds in order to
        catch a parse failure. The cause is kept and reachable.
        """
        with wrapping(ParseError):
            return _normalise(yaml.safe_load(data))

    def encode(self, value: object) -> bytes:
        """A structure into canonical bytes."""
        with wrapping(EncodeError):
            return _canonical(value).encode("utf-8")


YAML = YAMLCodec()


def _normalise(value: object) -> object:
    """What the parser produced, in the shape a JSON Schema validator expects.

    A mapping key that is not a string has no JSON equivalent, so it is refused
    rather than coerced: coercing invents a document nobody wrote.

    A TIMESTAMP IS THE ONE VALUE THAT IS COERCED, and it is the exception that
    proves the rule. YAML has a native timestamp type and JSON does not, so an
    unquoted 2026-01-01 decoded to a date and the structure stopped being the
    maps, lists and JSON scalars everything downstream assumes. It reached the
    validator, which has no type for it, and the save call then refused to write
    back a file the load call had just read.

    ISO 8601 is lossless for the value and is what the timestamp was written as,
    so the string carries everything the date did. Refusing instead would mean
    wrench cannot read an ordinary YAML file, and leaving it alone is what broke
    the round trip.
    """
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"mapping key {key!r} is {type(key).__name__}, not a string")
            out[key] = _normalise(item)
        return out
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    return value


def _at(where: str, error: ValueError) -> ValueError:
    """Prefix a failure with where in the structure it happened.

    A value with no canonical form is refused, and the caller needs to find it.
    Descending wraps each level, so the message reads `at key "a": at index 0:
    cannot write ...` and names the whole path rather than only the leaf. The Go
    pack words it identically, because a message that differs by pack is one
    consumers cannot be told to look for.
    """
    return ValueError(f"{where}: {error}")


def _canonical(value: object, depth: int = 0) -> str:
    """Emit one value in canonical form, indented for its depth.

    Written by hand rather than handed to a YAML library, because no emitter
    produces these bytes: block style throughout, keys sorted and quoted, and a
    scalar quoted exactly when it is a string. `testdata/canonical/` is what
    defines them, and all three packs are held to the same files.
    """
    pad = " " * (INDENT * depth)

    if isinstance(value, dict):
        return _mapping(value, depth, pad)
    if isinstance(value, list):
        return _sequence(value, depth, pad)
    return pad + _inline(value) + "\n"


def _spans_lines(value: object) -> bool:
    """Whether a value is written as an indented block rather than inline.

    A populated collection is; an empty one is not, because `{}` and `[]` are
    the canonical spelling for those and a block would be empty.
    """
    return isinstance(value, (dict, list)) and bool(value)


def _mapping(value: dict, depth: int, pad: str) -> str:
    """A mapping, one key to a line and keys sorted.

    Sorted because two producers emitting the same structure must emit the same
    bytes, and insertion order is not a property of the structure.
    """
    if not value:
        return pad + "{}\n"

    out = []
    for key in sorted(value):
        item = value[key]
        try:
            if _spans_lines(item):
                out.append(f"{pad}{_scalar(key)}:\n{_canonical(item, depth + 1)}")
            else:
                out.append(f"{pad}{_scalar(key)}: {_inline(item)}\n")
        except ValueError as err:
            raise _at(f"at key {_scalar(key)}", err) from err
    return "".join(out)


def _sequence(value: list, depth: int, pad: str) -> str:
    """A sequence, one entry to a dash, in the order it was given."""
    if not value:
        return pad + "[]\n"

    out = []
    for index, item in enumerate(value):
        try:
            out.append(_entry(item, depth, pad))
        except ValueError as err:
            raise _at(f"at index {index}", err) from err
    return "".join(out)


def _entry(item: object, depth: int, pad: str) -> str:
    """One sequence entry.

    The dash takes the place of the first line's indent, and the rest of the
    block keeps the indent it was rendered with, so a nested mapping under a
    dash lines up with the key beside it rather than with the dash.
    """
    if not _spans_lines(item):
        return f"{pad}- {_inline(item)}\n"

    nested = _canonical(item, depth + 1)
    first, _, rest = nested.partition("\n")
    out = f"{pad}- {first.strip()}\n"
    if rest:
        out += rest if rest.endswith("\n") else rest + "\n"
    return out


def _inline(value: object) -> str:
    """The one-line spelling of a value that has no children to indent.

    Only an empty collection and a scalar reach here. A populated one is written
    across lines by `_canonical`, because block style is the whole point.
    """
    if isinstance(value, dict):
        return "{}"
    if isinstance(value, list):
        return "[]"
    return _scalar(value)


# YAML'S OWN ESCAPE TABLE, matching what the Go pack emits byte for byte.
#
# FR-4.9. A raw control character in a quoted scalar is refused by a strict YAML
# reader and folded to a space by a lenient one, so a file carrying one is read
# differently depending on the reader. Escaping is the only answer that keeps
# every value writable, which
# `docs/DECISIONS/parity-is-reached-by-widening-never-by-refusing.md` requires.
#
# U+0085, U+2028 and U+2029 are here because YAML 1.1 makes all three line breaks
# and 1.2 does not, so which of them fold depends on the reader's version rather
# than on the character.
_YAML_NAMED = {
    0x00: r"\0",
    0x07: r"\a",
    0x08: r"\b",
    0x09: r"\t",
    0x0A: r"\n",
    0x0B: r"\v",
    0x0C: r"\f",
    0x0D: r"\r",
    0x1B: r"\e",
    0x22: r"\"",
    0x5C: "\\\\",
    0x85: r"\N",
    0x2028: r"\L",
    0x2029: r"\P",
    0xFEFF: "\\uFEFF",
}


FIRST_PRINTABLE = 0x20
DELETE = 0x7F
C1_FIRST = 0x80
C1_LAST = 0x9F


def _escape(value: str) -> str:
    r"""A string, escaped the way YAML spells escapes.

    Anything with a name gets it; the rest of C0, DEL and C1 get `\xNN` with
    uppercase hex, which is what the Go pack writes. Everything else is written
    as itself, including U+00A0 and U+200B, which no reader alters.
    """
    out = []
    for char in value:
        point = ord(char)
        named = _YAML_NAMED.get(point)
        if named is not None:
            out.append(named)
        elif point < FIRST_PRINTABLE or point == DELETE or C1_FIRST <= point <= C1_LAST:
            out.append(f"\\x{point:02X}")
        else:
            out.append(char)
    return "".join(out)


def _bare_scalar(value: object) -> str | None:
    """The scalars YAML and JSON spell identically, or None for anything else.

    Shared rather than written twice: null, the booleans, an integer and a float
    have one spelling across both formats, and a float's is FR-4.8's. What is
    left is the string, which each format quotes its own way, so the caller
    handles it and this returns None to say so.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return canonical_float_text(value)
    return None


def _scalar(value: object) -> str:
    """One scalar, spelled so its type survives being read back.

    A string is always quoted and everything else never is, which is what stops
    `no`, `1.20` and `null` returning as a boolean, a float and a nothing. A
    whole float keeps its decimal point for the same reason.
    """
    bare = _bare_scalar(value)
    if bare is not None:
        return bare
    if isinstance(value, str):
        return f'"{_escape(value)}"'
    raise ValueError(f"cannot write {type(value).__name__} in canonical form")
