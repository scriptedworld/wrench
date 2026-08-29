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
import os
from pathlib import Path
from typing import Any

import jsonschema
import jsonschema.exceptions
import jsonschema.validators
import referencing

from wrench._shipped import SHIPPED
from wrench.errors import SchemaError, ValidationError

# python/wrench/schema.py -> python/wrench -> python -> the repository root.
# Where the schemas live in a source checkout. The pack carries their text in
# `_shipped.py` and does not read this at run time; it is here so a test can
# hold the two against each other.
SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"

# The environment variable that lets a schema reference something outside the
# shipped set. Unset, which is the ordinary case, a $ref resolves only against
# the shipped schemas and the document's own fragments.
#
# THE UNSAFE BEHAVIOUR IS THE ONE YOU ASK FOR. Set to "1" it restores whatever
# the underlying implementation would do, which includes reading files.
#
# Measured 2026-08-27, before this existed: a $ref of
# "file:///tmp/x.schema.json" loaded that file off disk, so a schema's meaning
# depended on files outside it and a consumer could reference a local copy of a
# shipped schema instead of the shipped one. Nothing was fetched over the
# network, then or now, in either pack.
#
# THE ESCAPE HATCH IS ON BORROWED TIME AND SHOULD NOT BE BUILT ON. Setting it
# makes jsonschema emit:
#
#     DeprecationWarning: Automatically retrieving remote references can be a
#     security vulnerability and is discouraged by the JSON Schema
#     specifications. Relying on this behavior is deprecated and will shortly
#     become an error.
#
# So the library wrench binds already considers this a vulnerability and is
# removing it. The variable exists to unblock a caller who needs it today, not
# to be a supported mode, and it will stop working whether or not wrench changes.
ALLOW_EXTERNAL_REFS = "WRENCH_ALLOW_EXTERNAL_SCHEMA_REFS"


def _external_refs_allowed() -> bool:
    """Read on every compile rather than cached, so a test can set it and a long
    running process picks it up. It is one environment lookup."""
    return os.environ.get(ALLOW_EXTERNAL_REFS) == "1"


@functools.cache
def _shipped_documents() -> dict[str, dict]:
    """Every shipped schema, keyed by the `$id` it declares.

    `_shipped.py` is generated from the directory by `bin/generate-shipped.py`,
    so a schema added to `schemas/` is registered without this file being
    edited. Carrying the text is what lets the pack resolve its schemas without
    knowing where it was installed.
    """
    documents: dict[str, dict] = {}
    for name, text in SHIPPED.items():
        document = json.loads(text)
        declared = document.get("$id")
        if not isinstance(declared, str) or not declared:
            raise ValueError(f"wrench: shipped schema {name} declares no $id")
        documents[declared] = document
    if not documents:
        raise ValueError("wrench: no shipped schemas")
    return documents


@functools.cache
def _shipped_registry() -> referencing.Registry:
    """The shipped schemas as a resolution registry, so a `$ref` between two of
    them resolves locally and nothing reaches the network to validate a file."""
    return referencing.Registry().with_resources(
        (identifier, referencing.Resource.from_contents(document)) for identifier, document in _shipped_documents().items()
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
        """Hold the document and defer compiling it.

        `name` is the `$id` a failure will quote, never a filename: a relative
        filename resolves against whatever directory the process started in, and
        that path then travels inside an envelope.
        """
        self.name = name
        self._document = document
        self._registry = registry
        # Any, because jsonschema ships no stubs, so its validator type is not
        # knowable here and a checker should not pretend otherwise.
        self._validator: Any = None

    def validate(self, value: object) -> None:
        """Check a decoded structure, raising ValueError describing the first
        problem and where in the document it sits.

        Compiled here rather than at construction, so importing wrench costs
        nothing and a broken schema surfaces from the call that needed it.
        """
        # Held in a local through the lazy build, because reading the attribute
        # again after assigning it leaves a checker unable to prove it is no
        # longer None.
        validator = self._validator
        if validator is None:
            cls = jsonschema.validators.validator_for(self._document)
            cls.check_schema(self._document)
            validator = cls(self._document) if self._registry is None else cls(self._document, registry=self._registry)
            self._validator = validator

        # A reference this schema cannot resolve surfaces from the referencing
        # library as its own exception type, which is not the ValueError every
        # caller of this method is told to expect. Wrapping it keeps one error
        # contract and stops a third-party internal type reaching a consumer,
        # the way the Go pack wraps everything into its own.
        try:
            error = jsonschema.exceptions.best_match(validator.iter_errors(value))
        except Exception as unresolved:
            raise SchemaError(
                self.name,
                f"cannot resolve a reference: {unresolved}. "
                f"A schema may reference the shipped schemas and its own fragments, "
                f"and nothing else unless {ALLOW_EXTERNAL_REFS}=1",
            ) from unresolved

        if error is not None:
            where = "/".join(str(part) for part in error.absolute_path)
            at = f" at '/{where}'" if where else ""
            # ValidationError with no path: `validate` is handed a structure and
            # does not know which file it came from. `load_formatted_file` fills
            # the path in with `at()` rather than wrapping a second time.
            raise ValidationError(None, f"{self.name}{at}: {error.message}")


class _Shipped(Schema):
    """One of the schemas that ships with the library, read from disk the first
    time it is used.

    It is named by its `$id` alone, which is also how every other shipped schema
    references it. There is no filename here, so the two ways of naming one
    schema cannot disagree.
    """

    def __init__(self, identifier: str) -> None:
        """Named by its `$id` and nothing else, with an empty document standing
        in until first use. There is no filename here, so the two ways of naming
        one schema cannot disagree."""
        super().__init__(identifier, {})

    def validate(self, value: object) -> None:
        """Read the shipped set on first use, then validate as any schema does.

        The registry is attached here rather than at construction, so a shipped
        schema referencing another resolves without either being compiled until
        something needs one.
        """
        if not self._document:
            documents = _shipped_documents()
            if self.name not in documents:
                raise ValueError(f"wrench: no shipped schema declares {self.name}")
            self._document = documents[self.name]
            self._registry = _shipped_registry()
        super().validate(value)


def compile_schema(name: str, document: str | dict) -> Schema:
    """Turn a JSON Schema document into a Schema.

    The shipped set are not special: anything in the ecosystem can attach a
    schema to its own structured files and hand it to the same two calls.

    A caller's schema MAY reference a shipped one by its `$id`, because the
    shipped registry is handed to it. That is the case a consumer most wants: an
    adapter extending the envelope schema references it rather than copying it,
    and a copy is the drift FR-3.2 exists to prevent.

    It may reference NOTHING ELSE. See ALLOW_EXTERNAL_REFS.
    """
    # Neither `json.JSONDecodeError` nor `jsonschema.SchemaError` crosses this
    # boundary. A caller should not have to know which JSON parser or which
    # validator wrench binds in order to catch a schema that will not compile,
    # and both types were reaching consumers until this wrap. The cause is kept.
    try:
        parsed = json.loads(document) if isinstance(document, str) else document
    except Exception as err:
        raise SchemaError(name, err) from err

    if name in _shipped_documents():
        raise SchemaError(name, "a shipped schema cannot be redefined")

    try:
        cls = jsonschema.validators.validator_for(parsed)
        cls.check_schema(parsed)
    except Exception as err:
        raise SchemaError(name, err) from err

    registry = None if _external_refs_allowed() else _shipped_registry()
    return Schema(name, parsed, registry)


ENVELOPE_SCHEMA = _Shipped("https://scriptedworld.github.io/wrench/envelope.schema.json")

JIG_SCHEMA = _Shipped("https://scriptedworld.github.io/wrench/jig.schema.json")

MANIFEST_SCHEMA = _Shipped("https://scriptedworld.github.io/wrench/manifest.schema.json")

DEFINITIONS_SCHEMA = _Shipped("https://scriptedworld.github.io/wrench/definitions.schema.json")
