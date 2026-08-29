"""The schemas that ship with the library, named without a suffix.

    wrench.schemas.ENVELOPE
    wrench.schemas.JIG
    wrench.schemas.MANIFEST
    wrench.schemas.DEFINITIONS

The namespace carries what kind of thing these are, so the names do not have to.
`wrench.ENVELOPE_SCHEMA` says schema twice and reads worse the more of them
there are.

Not to be confused with `wrench.schema`, which is the machinery: the `Schema`
type, `compile_schema`, and the registry a `$ref` resolves against. This module
holds instances and nothing else.

Each is the same object as its older `*_SCHEMA` name, which is kept so a
consumer can move when it suits. Two names for one object cannot drift the way
two copies can, but only one of them is the spelling to write.
"""

from __future__ import annotations

from wrench.schema import DEFINITIONS_SCHEMA, ENVELOPE_SCHEMA, JIG_SCHEMA, MANIFEST_SCHEMA

__all__ = ["DEFINITIONS", "ENVELOPE", "JIG", "MANIFEST"]

#: The result envelope every producer in the ecosystem writes.
ENVELOPE = ENVELOPE_SCHEMA

#: The jig a runner reads a project's tasks from.
JIG = JIG_SCHEMA

#: What one task execution was going to be given, written before its command runs.
MANIFEST = MANIFEST_SCHEMA

#: The values a runner substitutes for a jig's placeholders.
DEFINITIONS = DEFINITIONS_SCHEMA
