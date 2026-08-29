"""A typed consumer of the Python pack, type-checked and never executed.

wrench ships `py.typed`, which asserts that a consumer running mypy against its
own code gets types from here rather than `import-not-found`. Checking the pack
alone cannot show that: the pack resolves its own imports whatever the marker
says, so the claim the marker makes is only tested from outside.

That is the failure this exists to catch, and it is not hypothetical. The marker
landed while the public API was unannotated, and a strict consumer traded
`cannot find wrench` for `wrench is untyped in 22 places`.

Nothing here asserts behaviour. The gate runs `mypy --strict` over it and the
suites cover what the calls do.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import wrench


def read_an_envelope(path: str) -> Any:
    """The shipped schema, codec and IO, which is the ordinary call."""
    return wrench.load_formatted_file(path, wrench.schemas.ENVELOPE, wrench.YAML, wrench.LOCAL_FILE)


def read_an_envelope_by_path_object(path: Path) -> Any:
    """The same call with `pathlib.Path`, which is what a Python caller reaches
    for and what the first real consumer passed.

    Here because a stub exercising only the types the pack expects keeps passing
    while a real caller's argument is wrong. That is how `path: str` survived:
    it ran correctly and nothing type-checked a `Path` against it.
    """
    return wrench.load_formatted_file(path, wrench.schemas.ENVELOPE, wrench.YAML, wrench.LOCAL_FILE)


def write_by_path_object(envelope: Any, directory: Path) -> None:
    """The save side with a path built the way a caller builds one."""
    wrench.save_yaml_file(envelope, directory / "output.yaml", wrench.schemas.ENVELOPE, wrench.LOCAL_FILE)


def write_an_envelope(envelope: Any, path: str) -> None:
    """The save side, through a wrapper rather than the core call."""
    wrench.save_yaml_file(envelope, path, wrench.schemas.ENVELOPE, wrench.LOCAL_FILE)


class MemoryReader:
    """A consumer's own reader, which is the point of FR-2.5a.

    It satisfies `wrench.Reader` structurally, so nothing here inherits from
    wrench and the pack still accepts it. A checker proves that at the call
    below rather than a test proving it at run time.
    """

    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self, path: str) -> bytes:
        del path
        return self._data


def read_without_a_filesystem(data: bytes) -> Any:
    """Substituting the IO, which a consumer does in its own tests."""
    reader: wrench.Reader = MemoryReader(data)
    return wrench.load_formatted_file("in-memory.yaml", wrench.schemas.JIG, wrench.YAML, reader)


def compile_a_consumers_own_schema(document: str) -> wrench.Schema:
    """A consumer's schema, which may reference a shipped one by its `$id`."""
    return wrench.compile_schema("https://example.invalid/mine.schema.json", document)


def name_the_failing_step(path: str) -> str:
    """The error family, matched once rather than by naming each type.

    A consumer catching `wrench.Error` reaches every failure the pack can
    produce, and `step` is the word it branches on. A property here where Go and
    Rust have a method, which is each pack spelling one thing its own way.
    """
    try:
        read_an_envelope(path)
    except wrench.Error as failure:
        return failure.step
    return "ok"


def each_codec(path: str) -> list[Any]:
    """Every shipped codec through the seam, so `Codec` is exercised as a type
    and not only as three concrete classes."""
    codecs: list[wrench.Codec] = [wrench.YAML, wrench.JSON, wrench.TOML]
    return [wrench.load_formatted_file(path, wrench.schemas.MANIFEST, codec, wrench.LOCAL_FILE) for codec in codecs]
