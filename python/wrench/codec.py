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
import math

import yaml

INDENT = 2


class YAMLCodec:
    """The format, knowing nothing about where the bytes came from."""

    def decode(self, data: bytes) -> object:
        """Bytes into maps, lists and scalars."""
        return _normalise(yaml.safe_load(data))

    def encode(self, value: object) -> bytes:
        """A structure into canonical bytes."""
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
                raise TypeError(
                    f"mapping key {key!r} is {type(key).__name__}, not a string"
                )
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
    pad = " " * (INDENT * depth)

    if isinstance(value, dict):
        if not value:
            return pad + "{}\n"
        out = []
        for key in sorted(value):
            item = value[key]
            try:
                if isinstance(item, (dict, list)) and item:
                    out.append(f"{pad}{_scalar(key)}:\n{_canonical(item, depth + 1)}")
                else:
                    out.append(f"{pad}{_scalar(key)}: {_inline(item)}\n")
            except ValueError as err:
                raise _at(f"at key {_scalar(key)}", err) from err
        return "".join(out)

    if isinstance(value, list):
        if not value:
            return pad + "[]\n"
        out = []
        for index, item in enumerate(value):
            try:
                if isinstance(item, (dict, list)) and item:
                    nested = _canonical(item, depth + 1)
                    # The dash takes the place of the first line's indent; the
                    # rest of the block keeps the indent it was rendered with.
                    first, _, rest = nested.partition("\n")
                    out.append(f"{pad}- {first.strip()}\n")
                    if rest:
                        out.append(rest if rest.endswith("\n") else rest + "\n")
                else:
                    out.append(f"{pad}- {_inline(item)}\n")
            except ValueError as err:
                raise _at(f"at index {index}", err) from err
        return "".join(out)

    return pad + _inline(value) + "\n"


def _inline(value: object) -> str:
    if isinstance(value, dict):
        return "{}"
    if isinstance(value, list):
        return "[]"
    return _scalar(value)


def _scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        # NaN and the infinities are refused: YAML can spell them and JSON
        # Schema cannot represent them, so writing one produces a file no
        # consumer in this ecosystem can validate.
        if math.isnan(value) or math.isinf(value):
            raise ValueError(f"cannot write {value} in canonical form")
        text = repr(value)
        # A whole float formats as "1", which reads back as an integer.
        return text if ("." in text or "e" in text or "E" in text) else text + ".0"
    if isinstance(value, str):
        escaped = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\t", "\\t")
            .replace("\r", "\\r")
        )
        return f'"{escaped}"'
    raise ValueError(f"cannot write {type(value).__name__} in canonical form")
