"""The YAML codec: bytes to a structure, and a structure to canonical bytes.

Canonical form is block style, one key to a line, keys sorted, and a scalar
quoted exactly when it is meant to be a string. Booleans and numbers stay bare.

Quoting marks intent, so `no`, `1.20` and `null` survive a round trip as the
strings they were and a boolean stays a boolean. Keys are sorted because a
mapping has no order of its own, and sorting is what makes two runs over the
same structure produce the same bytes.

**ruamel EMITS, AND THIS DECIDES FOUR THINGS.** The document is handed to
ruamel with the style named on each scalar, and ruamel turns it into text:
layout, indentation, escaping and line breaks are all its, and its escape table
is already the one this pack wants, `\\0 \\a \\b \\t \\n \\v \\f \\r \\e \\N \\L
\\P`, uppercase `\\x7F` and `\\uFEFF`.

The four are the adapters `packs-agree-on-structure-not-on-bytes` names, and
they preserve MEANING rather than layout: sort the keys, quote every string and
key, spell floats positionally, write null as the word. An emitter that walked
the structure producing text stood here until 2026-09-08 and is the thing that
decision retired.
"""

from __future__ import annotations

import datetime
import io
from typing import TYPE_CHECKING, Any, Protocol

from ruamel.yaml import YAML as _RuamelYAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString as _Quoted

if TYPE_CHECKING:
    from collections.abc import Callable

from wrench.errors import EncodeError, ParseError, wrapping
from wrench.float_text import canonical_float_text


class Codec(Protocol):
    """What the two calls require of a format.

    Named here so a consumer can annotate against the seam rather than against
    one of the three shipped codecs, which is what the Go and Rust packs give
    with their `Codec` interface and trait.

    `Any` and not `object` for the value: a decoded document is indexed by
    whatever reads it, and `object` would make every consumer cast. The Go pack
    spells the same choice `any`.
    """

    def decode(self, data: bytes) -> Any:
        """Bytes into maps, lists and JSON scalars."""
        ...

    def encode(self, value: Any) -> bytes:
        """A structure into canonical bytes."""
        ...


class YAMLCodec:
    """The format, knowing nothing about where the bytes came from."""

    def decode(self, data: bytes) -> object:
        """Bytes into maps, lists and scalars.

        The library's own exception types do not cross this boundary: a
        consumer should not have to know which YAML library wrench binds in
        order to catch a parse failure. The cause is kept and reachable.
        """
        with wrapping(ParseError):
            return _normalise(_reader().load(data.decode("utf-8")))

    def encode(self, value: object) -> bytes:
        """A structure into canonical bytes.

        The four adapters are applied to the structure, then ruamel writes it.
        Nothing here produces a character of YAML.
        """
        with wrapping(EncodeError):
            stream = io.StringIO()
            _writer().dump(_prepared(value), stream)
            return stream.getvalue().encode("utf-8")


YAML = YAMLCodec()


def _reader() -> _RuamelYAML:
    """A parser that builds plain maps, lists and scalars.

    `typ="safe"` refuses arbitrary tags, which is the property a library reading
    files from elsewhere needs, and returns builtins rather than ruamel's
    round-trip types so `_normalise` sees what every other pack's parser sees.
    """
    return _RuamelYAML(typ="safe")


def _writer() -> _RuamelYAML:
    """ruamel, set up to emit. Layout and escaping stay its; the adapters own
    ordering, quoting, float spelling and how a null is spelled.

    `width` is set past any real document because the default folds a long
    scalar across lines. That is legal YAML and reads back the same, but it puts
    a line break where the value had none and makes a diff noisy.
    """
    writer = _RuamelYAML()
    writer.default_flow_style = False
    writer.indent(mapping=INDENT, sequence=INDENT * 2, offset=INDENT)
    writer.width = 1 << 30
    writer.allow_unicode = True
    writer.representer.add_representer(float, _represent_float)
    writer.representer.add_representer(type(None), _represent_none)
    return writer


def _prepared(value: object) -> object:
    """Adapters one and two: sort the keys, and quote every string AND key.

    Quoting is what keeps `no`, `1.20` and `null` strings when they are read
    back. It covers keys because an unquoted `10:` is an integer key to a YAML
    1.1 reader, and a library left to choose spells it `'10'`, which is a third
    answer again.

    A key that is not a string is refused rather than written. Python's dict
    takes any hashable, and a bare `1:` would emit a document this codec's own
    decoder then refuses under FR-1.2.
    """
    if isinstance(value, dict):
        out = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise ValueError(f"cannot write a {type(key).__name__} key in canonical form")
            # The location is added on the way out, so a refusal names the key
            # or index it happened at rather than only the type. A schema over a
            # large document says nothing useful without one.
            try:
                out[_Quoted(key)] = _prepared(value[key])
            except ValueError as err:
                raise _at(f'at key "{key}"', err) from err
        return out
    if isinstance(value, list):
        prepared = []
        for index, item in enumerate(value):
            try:
                prepared.append(_prepared(item))
            except ValueError as err:
                raise _at(f"at index {index}", err) from err
        return prepared
    if isinstance(value, str):
        return _Quoted(value)
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        raise ValueError(f"cannot write {value} in canonical form")
    if not isinstance(value, (bool, int, float, type(None))):
        raise ValueError(f"cannot write {type(value).__name__} in canonical form")
    return value


def _represent_float(representer: Any, data: float) -> Any:
    """Adapter three: FR-4.8's positional decimal, never an exponent.

    Registered rather than emitted by hand, so ruamel still places the scalar in
    the document and this owns only its digits.
    """
    return representer.represent_scalar("tag:yaml.org,2002:float", canonical_float_text(data))


def _represent_none(representer: Any, _data: object) -> Any:
    """Adapter four: a null is the word rather than an empty.

    ruamel writes nothing after the colon by default, which reads back as None
    and is therefore spelling rather than meaning. It matters because a reader
    cannot tell an empty value from a missing one, and the other packs write the
    word.
    """
    return representer.represent_scalar("tag:yaml.org,2002:null", "null")


def _at(where: str, error: ValueError) -> ValueError:
    """The same refusal, carrying where in the document it happened.

    Prepended rather than appended, and only once per level, so a nested
    failure reads outermost first: `at key "a": at index 2: cannot write ...`.
    """
    return ValueError(f"{where}: {error}")


INDENT = 2

INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1


def widen(value: int) -> int | float:
    """An integer past int64, as the float every pack agrees on.

    PYTHON IS THE PACK THIS COSTS SOMETHING. Its integers are unbounded, so it
    alone decoded every value exactly and every other pack widened or refused,
    which meant one document meant different numbers depending on who read it.
    Go keeps int64 and reaches for uint64 above it; Rust keeps i64 and falls to
    f64. Neither can be asked to grow, so the agreement is reached by widening.

    THE LOSS IS DELIBERATE AND VISIBLE. 18446744073709551615 comes back spelled
    18446744073709552000.0, so a reader sees the precision go rather than
    receiving a different exact integer. Two inputs one apart can land on the
    same float, which is the plainest statement of the cost this makes.

    docs/DECISIONS/parity-is-reached-by-widening-never-by-refusing.md
    """
    if INT64_MIN <= value <= INT64_MAX:
        return value
    return float(value)


def _normalise(value: object, integer: Callable[[int], object] = widen) -> object:
    """What the parser produced, in the shape a JSON Schema validator expects.

    `integer` decides what happens to a value outside int64. YAML and JSON widen
    it to a float; TOML refuses, because its own spec requires an error and
    every other implementation throws one.

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
    if isinstance(value, int) and not isinstance(value, bool):
        return integer(value)
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"mapping key {key!r} is {type(key).__name__}, not a string")
            out[key] = _normalise(item, integer)
        return out
    if isinstance(value, (list, tuple)):
        return [_normalise(item, integer) for item in value]
    return value


def within_int64(value: int) -> int:
    """An integer TOML can carry, or a refusal.

    TOML v1.0.0 requires this: arbitrary 64-bit signed integers are handled
    losslessly, and "if an integer cannot be represented losslessly, an error
    must be thrown". Six independent parsers were asked and all six throw,
    three in Go and three in Rust.

    PYTHON IS THE WHOLE OF THE DEVIATION, and it is the ecosystem rather than
    one library: `tomllib` and `tomlkit` both accept the value, because Python
    integers are unbounded and neither range-checks. So there is nothing to swap
    to and the check belongs here.

    This is the one place widening is not the answer. `widen` exists because
    YAML and JSON leave the range open and the packs had to agree on something;
    TOML leaves nothing open.
    """
    if INT64_MIN <= value <= INT64_MAX:
        return value
    raise ValueError(f"{value} is out of range for TOML, which carries 64-bit signed integers")


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
