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

Every shipped schema is registered by its own `$id` before any of them compiles,
so one may reference another. A shape two files both need is then written once
instead of copied, which is the drift a shipped schema exists to prevent.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

import jsonschema
import jsonschema.exceptions
import jsonschema.validators
import referencing

# python/wrench/schema.py -> python/wrench -> python -> the repository root.
SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


@functools.lru_cache(maxsize=None)
def _shipped_documents() -> dict[str, dict]:
    """Every shipped schema, keyed by the `$id` it declares.

    The directory is read rather than a list of filenames kept here, so a schema
    added to `schemas/` is registered without this file being edited. A pack
    that has to be told about each new schema is a pack that silently ships one
    fewer than the other.
    """
    documents: dict[str, dict] = {}
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        document = json.loads(path.read_text())
        declared = document.get("$id")
        if not isinstance(declared, str) or not declared:
            raise ValueError(f"wrench: shipped schema {path.name} declares no $id")
        documents[declared] = document
    if not documents:
        raise ValueError(f"wrench: no shipped schemas under {SCHEMA_DIR}")
    return documents


@functools.lru_cache(maxsize=None)
def _shipped_registry() -> referencing.Registry:
    """The shipped schemas as a resolution registry, so a `$ref` between two of
    them resolves locally and nothing reaches the network to validate a file."""
    return referencing.Registry().with_resources(
        (identifier, referencing.Resource.from_contents(document))
        for identifier, document in _shipped_documents().items()
    )


class Schema:
    """A compiled schema. Validates the maps and lists a codec produced, rather
    than the text, so it is indifferent to how the file was serialised."""

    def __init__(
        self,
        name: str,
        document: dict,
        registry: referencing.Registry | None = None,
    ) -> None:
        self.name = name
        self._document = document
        self._registry = registry
        self._validator = None

    def validate(self, value: object) -> None:
        if self._validator is None:
            cls = jsonschema.validators.validator_for(self._document)
            cls.check_schema(self._document)
            if self._registry is None:
                self._validator = cls(self._document)
            else:
                self._validator = cls(self._document, registry=self._registry)
        error = jsonschema.exceptions.best_match(self._validator.iter_errors(value))
        if error is not None:
            where = "/".join(str(part) for part in error.absolute_path)
            at = f" at '/{where}'" if where else ""
            raise ValueError(f"{self.name}{at}: {error.message}")


class _Shipped(Schema):
    """One of the schemas that ships with the library, read from disk the first
    time it is used.

    It is named by its `$id` alone, which is also how every other shipped schema
    references it. There is no filename here, so the two ways of naming one
    schema cannot disagree.
    """

    def __init__(self, identifier: str) -> None:
        super().__init__(identifier, {})

    def validate(self, value: object) -> None:
        if not self._document:
            documents = _shipped_documents()
            if self.name not in documents:
                raise ValueError(f"wrench: no shipped schema declares {self.name}")
            self._document = documents[self.name]
            self._registry = _shipped_registry()
        super().validate(value)


def compile_schema(name: str, document: "str | dict") -> Schema:
    """Turn a JSON Schema document into a Schema.

    The shipped set are not special: anything in the ecosystem can attach a
    schema to its own structured files and hand it to the same two calls.
    """
    parsed = json.loads(document) if isinstance(document, str) else document
    cls = jsonschema.validators.validator_for(parsed)
    cls.check_schema(parsed)
    return Schema(name, parsed)


ENVELOPE_SCHEMA = _Shipped("https://scriptedworld.github.io/wrench/envelope.schema.json")

JIG_SCHEMA = _Shipped("https://scriptedworld.github.io/wrench/jig.schema.json")

MANIFEST_SCHEMA = _Shipped("https://scriptedworld.github.io/wrench/manifest.schema.json")

DEFINITIONS_SCHEMA = _Shipped(
    "https://scriptedworld.github.io/wrench/definitions.schema.json"
)
