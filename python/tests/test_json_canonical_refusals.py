"""What JSON canonical form refuses, and what it writes for an empty container.

These are the branches the rest of the suite goes round without going through.
Every one is an arm of a function the other tests exercise from the other side,
so only branch coverage sees them: line coverage reads them as covered because
the line above them ran.

The refusals cite FR-2.11 and not FR-4.6. The empty-container case is level
across the three packs and has a counterpart in each. The refusals are not, and
cannot be: a Go map is `map[string]any`, so a non-string key is unspellable
there, and a Rust `serde_json::Value` cannot hold a type outside JSON at all.
Only Python can be handed either. So these hold Python to the error family it
must raise, which is FR-2.11, and not to a canonical-form rule the other two
have no way to break.
"""

from __future__ import annotations

import re

import pytest

import wrench


# COVERS: FR-4.6 | edge
def test_an_empty_mapping_is_two_braces():
    """The early return, which the recursive path never reaches."""
    assert wrench.JSON.encode({}) == b"{}\n"


# COVERS: FR-4.6 | edge
def test_an_empty_sequence_is_two_brackets():
    """The same arm for a list. A newline between the brackets would be legal
    JSON and is not canonical form: an empty container has one spelling."""
    assert wrench.JSON.encode({"v": []}) == b'{\n  "v": []\n}\n'


# COVERS: FR-4.6 | edge
def test_a_nested_empty_container_keeps_the_short_spelling():
    """Depth does not change it, which makes it a property of the value and not
    of where the value sits."""
    encoded = wrench.JSON.encode({"a": {"b": {}}, "c": [[]]})
    assert b"{}" in encoded
    assert b"[]" in encoded


# COVERS: FR-2.11 | negative
def test_a_key_that_is_not_a_string_is_refused_by_name():
    """JSON has no spelling for a non-string key. Writing `1` as `"1"` would
    round-trip to a different document, so it is refused rather than coerced."""
    with pytest.raises(wrench.EncodeError) as raised:
        wrench.JSON.encode({1: "x"})
    assert "int" in str(raised.value)


# COVERS: FR-2.11 | negative
def test_a_value_of_an_unwritable_type_is_refused_by_name():
    """The refusal names the type, because `cannot write in canonical form` with
    no subject sends a reader looking through the whole document."""
    with pytest.raises(wrench.EncodeError) as raised:
        wrench.JSON.encode({"v": object()})
    assert "object" in str(raised.value)


# COVERS: FR-2.11 | negative
def test_a_set_is_refused_rather_than_written_as_a_list():
    """A set has no order, so writing one as a JSON array invents one. Canonical
    form cannot have a spelling that depends on iteration order."""
    with pytest.raises(wrench.EncodeError):
        wrench.JSON.encode({"v": {1, 2}})


# COVERS: FR-2.11 | negative
def test_a_shipped_schema_naming_nothing_shipped_says_which_name():
    """The guard on the lazy read, which fires only if the shipped set and the
    name it is asked for have come apart.

    Reached through the private class because no public entry point can produce
    it: the four shipped instances are module constants built from the generated
    set, so the name and the set agree by construction. That makes it a guard
    and not a case, and a guard nothing exercises has a message nobody has
    read. It names the name, because 'no shipped schema' with no subject says
    nothing a reader can act on.
    """
    absent = wrench.schema._Shipped("https://example.invalid/not-shipped.schema.json")  # noqa: SLF001
    with pytest.raises(ValueError, match=re.escape("not-shipped.schema.json")):
        absent.validate({})
