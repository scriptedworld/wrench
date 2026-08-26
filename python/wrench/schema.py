"""Schemas, and validating a decoded structure against one.

The schemas are the files in this repository's `schemas/` directory, read from
there rather than copied here. One copy is what stops a Go producer and a Python
producer drifting apart while both believe they conform.

Compiling is deferred until something validates against a schema, so importing
wrench costs nothing and a broken schema surfaces as an error from the call that
needed it rather than at import.

THE ID, NOT THE FILENAME, is what a schema is called in an error. A relative
filename resolves against whatever directory the process happened to start in,
which puts a local absolute path into a message that travels inside an envelope.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import jsonschema.exceptions
import jsonschema.validators

# python/wrench/schema.py -> python/wrench -> python -> the repository root.
SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


class Schema:
    """A compiled schema. Validates the maps and lists a codec produced, rather
    than the text, so it is indifferent to how the file was serialised."""

    def __init__(self, name: str, document: dict) -> None:
        self.name = name
        self._document = document
        self._validator = None

    def validate(self, value: object) -> None:
        if self._validator is None:
            cls = jsonschema.validators.validator_for(self._document)
            cls.check_schema(self._document)
            self._validator = cls(self._document)
        error = jsonschema.exceptions.best_match(self._validator.iter_errors(value))
        if error is not None:
            where = "/".join(str(part) for part in error.absolute_path)
            at = f" at '/{where}'" if where else ""
            raise ValueError(f"{self.name}{at}: {error.message}")


class _Shipped(Schema):
    """One of the schemas that ships with the library, read from disk the first
    time it is used."""

    def __init__(self, filename: str, identifier: str) -> None:
        self._filename = filename
        super().__init__(identifier, {})

    def validate(self, value: object) -> None:
        if not self._document:
            self._document = json.loads((SCHEMA_DIR / self._filename).read_text())
        super().validate(value)


def compile_schema(name: str, document: "str | dict") -> Schema:
    """Turn a JSON Schema document into a Schema.

    The shipped pair are not special: anything in the ecosystem can attach a
    schema to its own structured files and hand it to the same two calls.
    """
    parsed = json.loads(document) if isinstance(document, str) else document
    cls = jsonschema.validators.validator_for(parsed)
    cls.check_schema(parsed)
    return Schema(name, parsed)


ENVELOPE_SCHEMA = _Shipped(
    "envelope.schema.json",
    "https://scriptedworld.github.io/wrench/envelope.schema.json",
)

JIG_SCHEMA = _Shipped(
    "jig.schema.json",
    "https://scriptedworld.github.io/wrench/jig.schema.json",
)

MANIFEST_SCHEMA = _Shipped(
    "manifest.schema.json",
    "https://scriptedworld.github.io/wrench/manifest.schema.json",
)
