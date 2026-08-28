"""wrench reads, writes and validates the form of the ecosystem's structured
files.

File handling is two calls. Validation sits in the signature, so nothing reads
or writes without naming what the file must conform to. The codec is the format
and the reader or writer is the IO, declared separately, which puts the IO
boundary wholly outside the call.

    from wrench import (
        load_formatted_file, save_formatted_file,
        ENVELOPE_SCHEMA, YAML, LOCAL_FILE,
    )

    envelope = load_formatted_file(path, ENVELOPE_SCHEMA, YAML, LOCAL_FILE)
    save_formatted_file(envelope, path, ENVELOPE_SCHEMA, YAML, LOCAL_FILE)

The contract names these calls `load_formatted_file` and `save_formatted_file`,
and Python spells them the same way. What the packs share is behaviour, and Go
spells them `LoadFormattedFile` and `SaveFormattedFile` because that is how Go
spells things.
"""

from __future__ import annotations

from wrench.codec import YAML, YAMLCodec
from wrench.errors import (
    EncodeError,
    ParseError,
    ReadError,
    ValidationError,
    WrenchError,
    WriteError,
)
from wrench.localfile import LOCAL_FILE, LocalFileIO
from wrench.schema import (
    DEFINITIONS_SCHEMA,
    ENVELOPE_SCHEMA,
    JIG_SCHEMA,
    MANIFEST_SCHEMA,
    Schema,
    compile_schema,
)

__all__ = [
    "DEFINITIONS_SCHEMA",
    "ENVELOPE_SCHEMA",
    "JIG_SCHEMA",
    "LOCAL_FILE",
    "MANIFEST_SCHEMA",
    "YAML",
    "EncodeError",
    "LocalFileIO",
    "ParseError",
    "ReadError",
    "Schema",
    "ValidationError",
    "WrenchError",
    "WriteError",
    "YAMLCodec",
    "compile_schema",
    "load_formatted_file",
    "save_formatted_file",
]


def load_formatted_file(path, schema, codec, reader):
    """Read `path` through `reader`, decode it with `codec`, and validate the
    result against `schema`.

    A failure says which step failed: ReadError, ParseError and ValidationError
    are distinct because they have distinct causes and distinct fixes.
    """
    _require(schema, codec, reader, "reader")

    try:
        data = reader.read(path)
    except Exception as err:
        raise ReadError(path, err) from err

    try:
        value = codec.decode(data)
    except Exception as err:
        raise ParseError(path, err) from err

    try:
        schema.validate(value)
    except Exception as err:
        raise ValidationError(path, err) from err

    return value


def save_formatted_file(data, path, schema, codec, writer):
    """Validate `data` against `schema`, encode it with `codec` in canonical
    form, and write it to `path` through `writer`.

    Validation runs before the write, so a caller cannot put down a structure
    wrench would refuse to read back.
    """
    _require(schema, codec, writer, "writer")

    try:
        schema.validate(data)
    except Exception as err:
        raise ValidationError(path, err) from err

    try:
        encoded = codec.encode(data)
    except Exception as err:
        raise EncodeError(path, err) from err

    try:
        writer.write(path, encoded)
    except Exception as err:
        raise WriteError(path, err) from err


def _require(schema, codec, io, io_name: str) -> None:
    """The signature compels a schema. None is the one way round that in a
    language with no compile-time check, and it is refused here so the
    guarantee holds rather than being a convention."""
    if schema is None:
        raise ValueError("wrench: no schema given")
    if codec is None:
        raise ValueError("wrench: no codec given")
    if io is None:
        raise ValueError(f"wrench: no {io_name} given")
