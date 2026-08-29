"""What went wrong, said precisely enough to act on.

A failing call says which step failed. Reading, parsing and validating have
different causes and different fixes, so they are different types rather than
one message a caller has to read English out of.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


@contextlib.contextmanager
def wrapping(error: type[WrenchError]) -> Iterator[None]:
    """Turn whatever a bound library raises into `error`, keeping the cause.

    Every codec boundary needs the same three lines, and written out per codec
    they were duplicated closely enough for pylint to say so. One place also
    means the rule is stated once rather than re-derived.

    A `WrenchError` passes through untouched: it is already this contract, and
    wrapping it again would make a consumer unwrap twice to reach the cause.
    """
    try:
        yield
    except WrenchError:
        raise
    except Exception as err:
        raise error(None, err) from err


class WrenchError(Exception):
    """Anything wrench refuses. Carries the path it was working on.

    `path` is optional because the boundaries below the two calls do not know
    one: `YAML.decode` is handed bytes and `Schema.validate` a structure. Those
    raise with no path, and `at` fills it in when the failure passes back out
    through `load_formatted_file` or `save_formatted_file`.
    """

    def __init__(self, path: str | None, cause: BaseException | str) -> None:
        """Keep the path and the cause as attributes as well as in the message,
        so a consumer can report on them without parsing the string."""
        self.path = path
        self.cause = cause
        where = f" {path}" if path else ""
        super().__init__(f"wrench: {self._doing}{where}: {cause}")

    @property
    def step(self) -> str:
        """Which step failed, as a word a consumer can match on without matching
        the class.

        The three packs return the same six words, and bolt writes one into a
        reason's `kind`. It is deliberately not `_doing`: that is the gerund the
        message reads with, "parsing f.yaml", where this is the noun a consumer
        compares against. Rust keeps the same pair apart for the same reason.
        """
        return self._step

    def at(self, path: str) -> WrenchError:
        """The same failure, said with the path the caller named.

        Used instead of wrapping a second time: a `ParseError` from a codec and
        a `ParseError` from `load_formatted_file` are one failure, and nesting
        them would make a consumer unwrap twice to reach the cause.
        """
        return type(self)(path, self.cause)

    _doing = "handling"
    _step = "handling"


# NONE OF THESE SUBCLASS ValueError, AND THE TAXONOMY IS WHY.
#
# It looks like they should. `ValueError` is documented as "inappropriate
# argument value (of correct type)", `validate` means the value does not match
# its schema, and Python's own `json.JSONDecodeError` and
# `tomllib.TOMLDecodeError` are both `ValueError` subclasses.
#
# **But a validation failure is not always about the value.** Measured against
# `{"count": {"type": "integer", "minimum": 0}}`:
#
#     {"count": -1}        -1 is less than the minimum of 0     a VALUE problem
#     {"count": "three"}   'three' is not of type 'integer'     a TYPE problem
#
# The second is `TypeError` by Python's own definition, "inappropriate argument
# type", and `ValueError` explicitly excludes it with "(of correct type)". So
# `ValidationError` spans both and is a subclass of neither. Declaring it a
# `ValueError` would assert that every validation failure is a value-with-correct
# -type problem, which is false for a whole class of schema keyword.
#
# `EncodeError` is the same shape: a NaN has no canonical form because of its
# value, and an `object()` has none because of its type.
#
# **So wrench's six kinds are orthogonal to Python's value/type split**, and a
# consumer catches `WrenchError` or the kind it means. That is also why
# `except ValueError` stopped working when the wraps landed: it was never a
# statement about wrench's contract, only about what one library happened to
# raise.
#
# `read` and `write` are not `OSError` either, and for a related reason: OSError
# carries an errno and filename contract, and a `Reader` may be a network, a
# buffer or a test stub rather than an operating system.


class ReadError(WrenchError):
    """The file could not be read at all. The reader failed before any question
    of format or conformance arose."""

    _doing = "reading"
    _step = "read"


class ParseError(WrenchError):
    """The codec could not turn the bytes into a structure. The file is not the
    format it was read as."""

    _doing = "parsing"
    _step = "parse"


class ValidationError(WrenchError):
    """The structure parsed and does not match its schema. The right format and
    the wrong shape, which is a different condition with a different fix."""

    _doing = "validating"
    _step = "validate"


class EncodeError(WrenchError):
    """A valid structure could not be rendered in the codec's canonical form."""

    _doing = "encoding"
    _step = "encode"


class WriteError(WrenchError):
    """The bytes could not be put in place."""

    _doing = "writing"
    _step = "write"


class SchemaError(WrenchError):
    """The schema itself will not compile.

    Distinct from `ValidationError`, which is a document failing a schema that
    is fine. This is the schema being unreadable or not a valid JSON Schema, so
    nothing can be validated against it at all and the fix is to the schema
    rather than to any document.

    It is the type `clank gate/30` recorded as missing when `compile_schema` was
    found leaking `json.JSONDecodeError` and `jsonschema.SchemaError`.
    """

    _doing = "compiling"
    _step = "schema"
