"""The TOML codec: bytes to a structure, and a structure to canonical bytes.

TOML is the one format wrench ships that cannot hold everything the other two
can, so two questions had to be answered rather than implemented around. Both
are answered the way the contract already answers them elsewhere.

**A null is refused rather than substituted.** TOML has no null. FR-4.1 says a
value with no canonical form is refused rather than guessed at, and that is the
same situation: writing `""` or omitting the key invents a document nobody
wrote, and a consumer reading it back gets a different structure than was saved.

**A date decodes to its ISO 8601 string.** FR-2.9 says a decoder produces maps,
lists and JSON scalars and nothing else. TOML has native date, time and datetime
types, exactly as YAML does, and the YAML codec already coerces those for the
same reason: the value reaches a JSON Schema validator that has no type for it,
and a structure that loads but cannot be saved back is what the rule prevents.
ISO 8601 is lossless for the value and is what the file already said.

**A TOML document is a table.** There is no top-level scalar or array in the
format, so encoding one is refused rather than wrapped in an invented key.
"""

from __future__ import annotations

import datetime
import tomllib

from wrench.codec import DELETE, FIRST_PRINTABLE, _normalise
from wrench.errors import EncodeError, ParseError, wrapping
from wrench.float_text import canonical_float_text


class TOMLCodec:
    """The format, knowing nothing about where the bytes came from."""

    def decode(self, data: bytes) -> object:
        """Bytes into maps, lists and scalars.

        `_normalise` is shared with the YAML codec rather than reimplemented,
        because the coercion rule is the contract's and not one format's: both
        formats have native temporal types and JSON has none.

        `tomllib.TOMLDecodeError` does not cross this boundary; the cause is
        kept and reachable.
        """
        with wrapping(ParseError):
            return _normalise(tomllib.loads(data.decode("utf-8")))

    def encode(self, value: object) -> bytes:
        """A structure into canonical bytes, keys sorted.

        WRITTEN BY HAND, for the reason the YAML emitter is: no TOML library
        produces these bytes. Measured 2026-08-28, the same structure through
        `tomli_w` and Go's `BurntSushi/toml` differed in array layout and in
        indentation under a table, so two packs using their own library disagree
        about canonical form, which is the failure wrench exists to prevent.

        The form: scalars first, sorted; then each sub-table as a `[path]`
        section, sorted; arrays inline on one line; no indentation inside a
        table.
        """
        if not isinstance(value, dict):
            raise EncodeError(None, f"cannot write {type(value).__name__} in canonical form: a TOML document is a table")
        with wrapping(EncodeError):
            _refuse_null(value, "")
            return "".join(_table(value, [])).encode("utf-8")


def _refuse_null(value: object, where: str) -> None:
    """Refuse a null anywhere in the structure, naming where it sits.

    Checked before encoding rather than left to the writer, because the writer's
    own message names a type rather than a path, and a caller with a nested
    document needs to find the key.
    """
    if value is None:
        at = f" at {where}" if where else ""
        raise ValueError(f"cannot write null in canonical form{at}: TOML has no null")
    if isinstance(value, dict):
        for key, item in value.items():
            _refuse_null(item, f"{where}.{key}" if where else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _refuse_null(item, f"{where}[{index}]")


def _table(value: dict, path: list[str]) -> list[str]:
    """One table: its scalars, then its sub-tables, each sorted.

    Scalars first because TOML binds a bare key to the most recent `[header]`,
    so a scalar written after a sub-table would land inside it. That is a
    correctness rule rather than a layout preference.
    """
    out: list[str] = []
    if path:
        out.append(f"[{'.'.join(_key(part) for part in path)}]\n")

    sections = []
    for name in sorted(value):
        item = value[name]
        if isinstance(item, dict) or _is_table_array(item):
            sections.append(name)
        else:
            out.append(f"{_key(name)} = {_inline(item)}\n")

    for name in sections:
        item = value[name]
        deeper = [*path, name]
        if isinstance(item, dict):
            out.append("\n")
            out.extend(_table(item, deeper))
            continue
        # An array of tables is repeated `[[path]]` sections. TOML has no inline
        # form for one, so this is the only spelling available rather than a
        # choice between two.
        header = ".".join(_key(part) for part in deeper)
        for entry in item:
            out.append(f"\n[[{header}]]\n")
            out.extend(_table(entry, [])[0:])
    return out


def _is_table_array(value: object) -> bool:
    """A non-empty list whose every item is a table.

    Empty stays inline as `[]`, because an empty array of tables and an empty
    array of anything else are the same document and `[]` is the shorter of the
    two spellings. A mixed list is not a table array and is refused by
    `_inline`, which is where the message about it belongs.
    """
    return bool(value) and isinstance(value, list) and all(isinstance(i, dict) for i in value)


def _key(name: object) -> str:
    """A key, bare where TOML allows it and quoted where it does not."""
    if not isinstance(name, str):
        raise TypeError(f"mapping key {name!r} is {type(name).__name__}, not a string")
    if name and all(c.isalnum() or c in "_-" for c in name):
        return name
    return _string(name)


def _inline(value: object) -> str:
    """A value on one line: a scalar, or an array of them."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return _number(value)
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return _string(value.isoformat())
    if isinstance(value, list):
        return "[" + ", ".join(_inline(item) for item in value) + "]"
    if isinstance(value, dict):
        # An inline table would be a second way to spell a sub-table, and two
        # spellings of one thing is what canonical form exists to remove.
        raise ValueError("cannot write a table inline in canonical form")
    raise ValueError(f"cannot write {type(value).__name__} in canonical form")


def _number(value: float) -> str:
    """A number, with a float in the spelling every codec shares.

    Kept in step with the YAML and JSON codecs deliberately: a float spelled
    differently per format is the same defect as one that reads back as an
    integer. FR-4.8.
    """
    if isinstance(value, int):
        return str(value)
    return canonical_float_text(value)


# TOML'S OWN ESCAPE TABLE, which is not YAML's. FR-4.9.
#
# TOML requires escaping the quote, the backslash and every control character
# except tab, and it offers far fewer names than YAML: there is no `\e`, no `\v`,
# no `\0` and no `\x`. So anything without a name here becomes `\uXXXX`, which is
# the format's own spelling rather than a second answer to YAML's question.
#
# C1 is deliberately left raw. TOML does not require escaping it and all three
# parsers round trip it, so escaping would be this pack inventing a rule.
_TOML_NAMED = {
    0x08: r"\b",
    0x09: r"\t",
    0x0A: r"\n",
    0x0C: r"\f",
    0x0D: r"\r",
    0x22: r"\"",
    0x5C: "\\\\",
}


def _string(value: str) -> str:
    r"""A basic string, escaped the way TOML spells escapes.

    Anything with a name gets it and every other control character becomes
    `\uXXXX`. C1 is left raw, which TOML permits and every parser round trips.
    """
    out = []
    for char in value:
        point = ord(char)
        named = _TOML_NAMED.get(point)
        if named is not None:
            out.append(named)
        elif point < FIRST_PRINTABLE or point == DELETE:
            out.append(f"\\u{point:04X}")
        else:
            out.append(char)
    return '"' + "".join(out) + '"'


TOML = TOMLCodec()
