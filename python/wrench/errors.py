"""What went wrong, said precisely enough to act on.

A failing call says which step failed. Reading, parsing and validating have
different causes and different fixes, so they are different types rather than
one message a caller has to read English out of.
"""

from __future__ import annotations


class WrenchError(Exception):
    """Anything wrench refuses. Carries the path it was working on."""

    def __init__(self, path: str, cause: BaseException | str) -> None:
        self.path = path
        self.cause = cause
        super().__init__(f"wrench: {self._doing} {path}: {cause}")

    _doing = "handling"


class ReadError(WrenchError):
    """The file could not be read at all. The reader failed before any question
    of format or conformance arose."""

    _doing = "reading"


class ParseError(WrenchError):
    """The codec could not turn the bytes into a structure. The file is not the
    format it was read as."""

    _doing = "parsing"


class ValidationError(WrenchError):
    """The structure parsed and does not match its schema. The right format and
    the wrong shape, which is a different condition with a different fix."""

    _doing = "validating"


class EncodeError(WrenchError):
    """A valid structure could not be rendered in the codec's canonical form."""

    _doing = "encoding"


class WriteError(WrenchError):
    """The bytes could not be put in place."""

    _doing = "writing"
