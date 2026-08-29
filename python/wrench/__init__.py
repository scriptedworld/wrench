"""wrench reads, writes and validates the form of the ecosystem's structured
files.

File handling is two calls. Validation sits in the signature, so nothing reads
or writes without naming what the file must conform to. The codec is the format
and the reader or writer is the IO, declared separately, which puts the IO
boundary wholly outside the call.

    from wrench import (
        load_formatted_file, save_formatted_file,
        schemas, YAML, LOCAL_FILE,
    )

    envelope = load_formatted_file(path, schemas.ENVELOPE, YAML, LOCAL_FILE)
    save_formatted_file(envelope, path, schemas.ENVELOPE, YAML, LOCAL_FILE)

`schemas.ENVELOPE` is the spelling to write. `ENVELOPE_SCHEMA` is the same
object under its older name and is kept while consumers move.

The contract names these calls `load_formatted_file` and `save_formatted_file`,
and Python spells them the same way. What the packs share is behaviour, and Go
spells them `LoadFormattedFile` and `SaveFormattedFile` because that is how Go
spells things.
"""

from __future__ import annotations

import os
from typing import Any

from wrench import schemas
from wrench.codec import YAML, Codec, YAMLCodec
from wrench.errors import (
    EncodeError,
    Error,
    ParseError,
    ReadError,
    SchemaError,
    UsageError,
    ValidationError,
    WriteError,
)
from wrench.json_codec import JSON, JSONCodec
from wrench.localfile import LOCAL_FILE, LocalFileIO, Reader, Writer
from wrench.schema import (
    DEFINITIONS_SCHEMA,
    ENVELOPE_SCHEMA,
    JIG_SCHEMA,
    MANIFEST_SCHEMA,
    Schema,
    compile_schema,
)
from wrench.toml_codec import TOML, TOMLCodec

# What a Python caller may hand the two calls. The seams stay `str`, and a path
# is normalised once on the way in. See
# docs/DECISIONS/each-pack-spells-the-calls-its-own-way.md.
StrPath = str | os.PathLike[str]

__all__ = [
    "DEFINITIONS_SCHEMA",
    "ENVELOPE_SCHEMA",
    "JIG_SCHEMA",
    "JSON",
    "LOCAL_FILE",
    "MANIFEST_SCHEMA",
    "TOML",
    "YAML",
    "Codec",
    "EncodeError",
    "Error",
    "JSONCodec",
    "LocalFileIO",
    "ParseError",
    "ReadError",
    "Reader",
    "Schema",
    "SchemaError",
    "TOMLCodec",
    "UsageError",
    "ValidationError",
    "WriteError",
    "Writer",
    "YAMLCodec",
    "compile_schema",
    "load_formatted_file",
    "load_json_file",
    "load_toml_file",
    "load_yaml_file",
    "save_formatted_file",
    "save_json_file",
    "save_toml_file",
    "save_yaml_file",
    "schemas",
]


def load_formatted_file(path: StrPath, schema: Schema, codec: Codec, reader: Reader) -> Any:
    """Read `path` through `reader`, decode it with `codec`, and validate the
    result against `schema`.

    A failure says which step failed: ReadError, ParseError and ValidationError
    are distinct because they have distinct causes and distinct fixes.
    """
    _require(schema, codec, reader, "reader")
    named = _path(path)

    try:
        data = reader.read(named)
    except Error as err:
        # Already wrench's, from a codec or a schema that has no
        # path. Fill it in rather than wrap a second time.
        raise err.at(named) from err.__cause__ or err
    except Exception as err:
        raise ReadError(named, err) from err

    try:
        value = codec.decode(data)
    except Error as err:
        raise err.at(named) from err.__cause__ or err
    except Exception as err:
        raise ParseError(named, err) from err

    try:
        schema.validate(value)
    except Error as err:
        raise err.at(named) from err.__cause__ or err
    except Exception as err:
        raise ValidationError(named, err) from err

    return value


def save_formatted_file(data: Any, path: StrPath, schema: Schema, codec: Codec, writer: Writer) -> None:
    """Validate `data` against `schema`, encode it with `codec` in canonical
    form, and write it to `path` through `writer`.

    Validation runs before the write, so a caller cannot put down a structure
    wrench would refuse to read back.
    """
    _require(schema, codec, writer, "writer")
    named = _path(path)

    try:
        schema.validate(data)
    except Error as err:
        # Already wrench's, from a codec or a schema that has no
        # path. Fill it in rather than wrap a second time.
        raise err.at(named) from err.__cause__ or err
    except Exception as err:
        raise ValidationError(named, err) from err

    try:
        encoded = codec.encode(data)
    except Error as err:
        raise err.at(named) from err.__cause__ or err
    except Exception as err:
        raise EncodeError(named, err) from err

    try:
        writer.write(named, encoded)
    except Error as err:
        raise err.at(named) from err.__cause__ or err
    except Exception as err:
        raise WriteError(named, err) from err


# ---- per-format wrappers ----------------------------------------------------
#
# These add no behaviour. Each supplies one argument to the two calls above, so
# validation still sits in the signature and the seam is unchanged.
#
# NAMED RATHER THAN INFERRED FROM THE SUFFIX. Choosing a parser by filename makes
# behaviour depend on what a file is called, so renaming one would silently
# change how it is read. FR-2.2 exists to remove exactly that implicitness.


def load_yaml_file(path: StrPath, schema: Schema, reader: Reader) -> Any:
    """Load a YAML file, validated against `schema`."""
    return load_formatted_file(path, schema, YAML, reader)


def save_yaml_file(data: Any, path: StrPath, schema: Schema, writer: Writer) -> None:
    """Save a structure as canonical YAML, validated against `schema`."""
    save_formatted_file(data, path, schema, YAML, writer)


def load_json_file(path: StrPath, schema: Schema, reader: Reader) -> Any:
    """Load a JSON file, validated against `schema`."""
    return load_formatted_file(path, schema, JSON, reader)


def save_json_file(data: Any, path: StrPath, schema: Schema, writer: Writer) -> None:
    """Save a structure as canonical JSON, validated against `schema`."""
    save_formatted_file(data, path, schema, JSON, writer)


def load_toml_file(path: StrPath, schema: Schema, reader: Reader) -> Any:
    """Load a TOML file, validated against `schema`.

    A native date, time or datetime decodes to its ISO 8601 string, which is what
    FR-2.9 requires of every decoder.
    """
    return load_formatted_file(path, schema, TOML, reader)


def save_toml_file(data: Any, path: StrPath, schema: Schema, writer: Writer) -> None:
    """Save a structure as canonical TOML, validated against `schema`.

    Refuses a structure containing null, which TOML cannot spell, and refuses one
    that is not a table, which TOML has no way to be.
    """
    save_formatted_file(data, path, schema, TOML, writer)


def _path(path: StrPath) -> str:
    """A path as the one spelling the seams and the error messages use.

    A value that is neither raises `usage` and not `read`, so a caller's mistake
    is not reported as a filesystem failure.
    """
    try:
        return os.fspath(path)
    except TypeError as err:
        raise UsageError(None, f"path is {type(path).__name__}, not a string or path") from err


def _require(schema: object, codec: object, io: object, io_name: str) -> None:
    """The signature compels a schema. None is the one way round that in a
    language with no compile-time check, and it is refused here so the
    guarantee holds rather than being a convention.

    Typed as `object` because the whole point is to receive what the annotations
    say cannot arrive. Rust needs no equivalent: there the same call does not
    compile, which is why it is the one pack that cannot raise `usage`.
    """
    if schema is None:
        raise UsageError(None, "no schema given")
    if codec is None:
        raise UsageError(None, "no codec given")
    if io is None:
        raise UsageError(None, f"no {io_name} given")
