"""How a `$ref` is handled, and what a schema keyword means in each of its roles.

The cases here are the cases the Go and Rust suites run. The packs were measured
against each other on 2026-09-03 before any of these were written, and a
divergence here is a divergence in the contract rather than in one binding.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

import wrench

# The sentence FR-3.10d requires of every pack. Held as a constant so a change to
# the wording fails a test rather than drifting quietly through three
# repositories' worth of consumers.
REFUSAL = "a schema may reference the shipped schemas and its own fragments, and nothing else"

# A schema that really is on disk, so "it was not read" is a measurement rather
# than the absence of a target. It requires a property no instance here carries,
# so a document validated against it would fail loudly.
#
# The path is derived rather than written as `/tmp/...`, which is what S108 asks
# for and is right here for a second reason: it has to be somewhere a `$ref`
# could plausibly reach, and the platform's own temporary directory is that
# wherever the suite runs.
REACHABLE = str(Path(tempfile.gettempdir()) / "wrench-reachable.schema.json")

PERMISSIVE = json.dumps({"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"})


@pytest.fixture(autouse=True)
def _seed_reachable_schema():
    with Path(REACHABLE).open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "required": ["proof_it_resolved"],
            },
            handle,
        )


def outcome(name, schema_body, instance):
    """What happened, rather than an assertion, so a table states its own
    expectation."""
    try:
        schema = wrench.compile_schema(name, schema_body)
    except wrench.SchemaError as e:
        return "schema", str(e)
    try:
        schema.validate(instance)
    except wrench.SchemaError as e:
        return "schema", str(e)
    except wrench.ValidationError as e:
        return "validate", str(e)
    return "accepted", ""


# COVERS: FR-3.10c | negative
@pytest.mark.parametrize(
    ("what", "instance"),
    [
        ("a $ref at a file that exists", {"$ref": f"file://{REACHABLE}"}),
        ("a $ref at an http url", {"$ref": "http://example.invalid/x.schema.json"}),
        ("an $id", {"$id": "https://example.invalid/other"}),
        ("a $schema", {"$schema": "https://json-schema.org/draft/2020-12/schema"}),
        (
            "a document that is a schema",
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "https://example.invalid/embedded",
                "$ref": f"file://{REACHABLE}",
            },
        ),
    ],
)
def test_a_keyword_in_an_instance_is_data(what, instance):
    """The schema keywords are ordinary keys in a document being validated, and a
    data file is allowed to carry them. The file this points at EXISTS, so an
    implementation that resolved it is caught here rather than passing for want
    of a target."""
    got, detail = outcome("https://example.invalid/s.schema.json", PERMISSIVE, instance)
    assert got == "accepted", f"{what} in an instance was interpreted: {got}: {detail}"


# COVERS: FR-3.10a | positive
@pytest.mark.parametrize(
    ("what", "body"),
    [
        (
            "a pointer into $defs",
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$defs": {"tight": {"type": "string", "minLength": 3}},
                "type": "object",
                "properties": {"a": {"$ref": "#/$defs/tight"}},
            },
        ),
        (
            "an $anchor",
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$defs": {"t": {"$anchor": "tight", "type": "string", "minLength": 3}},
                "type": "object",
                "properties": {"a": {"$ref": "#tight"}},
            },
        ),
    ],
)
def test_a_reference_within_the_document_resolves(what, body):
    """Both spellings of an internal reference, each asserted by its VIOLATION:
    an accepted document says nothing, because a $ref that silently contributed
    no constraint would accept it too."""
    document = json.dumps(body)
    name = "https://example.invalid/s.schema.json"

    got, detail = outcome(name, document, {"a": "abc"})
    assert got == "accepted", f"{what} refused a document it should take: {detail}"

    got, _ = outcome(name, document, {"a": "x"})
    assert got == "validate", f"{what} did not constrain, so the reference resolved to nothing"


# COVERS: FR-3.10b, FR-3.10d | negative
def test_a_refusal_names_the_resolved_reference():
    """A relative reference resolves against the document's $id, so the text and
    the reference are different strings. Naming the text would send a reader
    looking for something that is not what failed.

    This also pins that the $id wins over the compile name: the name here is a
    bare filename, and were IT the base the reference would resolve to a path
    rather than to elsewhere.invalid."""
    body = json.dumps(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://elsewhere.invalid/root.schema.json",
            "$ref": "sibling.schema.json",
        }
    )
    got, detail = outcome("mine.schema.json", body, {"anything": 1})

    assert got == "schema", f"a reference outside the shipped set resolved: {got}"
    assert "https://elsewhere.invalid/sibling.schema.json" in detail, detail
    assert REFUSAL in detail, detail


# COVERS: FR-3.10d | negative
@pytest.mark.parametrize(
    ("what", "ref"),
    [
        ("an http url", "http://example.invalid/x.schema.json"),
        ("an https url", "https://example.invalid/x.schema.json"),
        ("a file url", f"file://{REACHABLE}"),
        ("an absolute path", REACHABLE),
        ("a relative path", "sibling.schema.json"),
        ("an unshipped wrench", "https://scriptedworld.github.io/wrench/not-shipped.schema.json"),
    ],
)
def test_every_refused_form_gives_the_same_sentence(what, ref):
    """One sentence for every shape a reference can take, so a consumer matching
    on the failure does not need a list of the ways it can be spelled."""
    body = json.dumps({"$schema": "https://json-schema.org/draft/2020-12/schema", "$ref": ref})
    got, detail = outcome("https://example.invalid/s.schema.json", body, {"anything": 1})

    assert got == "schema", f"{what} resolved rather than being refused"
    assert REFUSAL in detail, f"{what} was refused in different words: {detail}"


# COVERS: FR-3.10 | negative
@pytest.mark.parametrize(
    "name",
    [
        "WRENCH_ALLOW_EXTERNAL_SCHEMA_REFS",
        "WRENCH_ALLOW_LOCAL_SCHEMA_REFS",
        "WRENCH_ALLOW_NET_SCHEMA_REFS",
    ],
)
def test_no_environment_variable_opens_a_reference(name):
    """WRENCH_ALLOW_EXTERNAL_SCHEMA_REFS was documented before it was retired on
    2026-09-03, so somebody may still set it. It meant three different things
    while it existed: this pack fetched over HTTP and read files, Go read files,
    and Rust did nothing at all.

    One variable per case rather than a loop, so a leftover from an earlier
    iteration cannot be what the next one measures.

    os.environ directly rather than monkeypatch: this arranges an input, and
    reaching for a patching fixture to do it blurs the line with mocking the code
    under test."""
    body = json.dumps(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": f"file://{REACHABLE}",
        }
    )
    previous = os.environ.get(name)
    os.environ[name] = "1"
    try:
        got, _ = outcome("https://example.invalid/s.schema.json", body, {"anything": 1})
        assert got == "schema", f"{name}=1 opened a reference"
    finally:
        if previous is None:
            del os.environ[name]
        else:
            os.environ[name] = previous
