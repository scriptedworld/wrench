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
    SchemaError,
    ValidationError,
    WrenchError,
    WriteError,
)
from wrench.json_codec import JSON, JSONCodec
from wrench.localfile import LOCAL_FILE, LocalFileIO
from wrench.schema import (
    DEFINITIONS_SCHEMA,
    ENVELOPE_SCHEMA,
    JIG_SCHEMA,
    MANIFEST_SCHEMA,
    Schema,
    compile_schema,
)
from wrench.toml_codec import TOML, TOMLCodec

__all__ = [
    "DEFINITIONS_SCHEMA",
    "ENVELOPE_SCHEMA",
    "JIG_SCHEMA",
    "JSON",
    "LOCAL_FILE",
    "MANIFEST_SCHEMA",
    "TOML",
    "YAML",
    "EncodeError",
    "JSONCodec",
    "LocalFileIO",
    "ParseError",
    "ReadError",
    "Schema",
    "SchemaError",
    "TOMLCodec",
    "ValidationError",
    "WrenchError",
    "WriteError",
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
    except WrenchError as err:
        # Already wrench's, from a codec or a schema that has no
        # path. Fill it in rather than wrap a second time.
        raise err.at(path) from err.__cause__ or err
    except Exception as err:
        raise ReadError(path, err) from err

    try:
        value = codec.decode(data)
    except WrenchError as err:
        # Already wrench's, from a codec or a schema that has no
        # path. Fill it in rather than wrap a second time.
        raise err.at(path) from err.__cause__ or err
    except Exception as err:
        raise ParseError(path, err) from err

    try:
        schema.validate(value)
    except WrenchError as err:
        # Already wrench's, from a codec or a schema that has no
        # path. Fill it in rather than wrap a second time.
        raise err.at(path) from err.__cause__ or err
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
    except WrenchError as err:
        # Already wrench's, from a codec or a schema that has no
        # path. Fill it in rather than wrap a second time.
        raise err.at(path) from err.__cause__ or err
    except Exception as err:
        raise ValidationError(path, err) from err

    try:
        encoded = codec.encode(data)
    except WrenchError as err:
        # Already wrench's, from a codec or a schema that has no
        # path. Fill it in rather than wrap a second time.
        raise err.at(path) from err.__cause__ or err
    except Exception as err:
        raise EncodeError(path, err) from err

    try:
        writer.write(path, encoded)
    except WrenchError as err:
        # Already wrench's, from a codec or a schema that has no
        # path. Fill it in rather than wrap a second time.
        raise err.at(path) from err.__cause__ or err
    except Exception as err:
        raise WriteError(path, err) from err


# ---- per-format wrappers ----------------------------------------------------
#
# These add no behaviour. Each supplies one argument to the two calls above, so
# validation still sits in the signature and the seam is unchanged.
#
# NAMED RATHER THAN INFERRED FROM THE SUFFIX. Choosing a parser by filename makes
# behaviour depend on what a file is called, so renaming one would silently
# change how it is read. FR-2.2 exists to remove exactly that implicitness.


def load_yaml_file(path, schema, reader):
    """Load a YAML file, validated against `schema`."""
    return load_formatted_file(path, schema, YAML, reader)


def save_yaml_file(data, path, schema, writer):
    """Save a structure as canonical YAML, validated against `schema`."""
    save_formatted_file(data, path, schema, YAML, writer)


def load_json_file(path, schema, reader):
    """Load a JSON file, validated against `schema`."""
    return load_formatted_file(path, schema, JSON, reader)


def save_json_file(data, path, schema, writer):
    """Save a structure as canonical JSON, validated against `schema`."""
    save_formatted_file(data, path, schema, JSON, writer)


def load_toml_file(path, schema, reader):
    """Load a TOML file, validated against `schema`.

    A native date, time or datetime decodes to its ISO 8601 string, which is what
    FR-2.9 requires of every decoder.
    """
    return load_formatted_file(path, schema, TOML, reader)


def save_toml_file(data, path, schema, writer):
    """Save a structure as canonical TOML, validated against `schema`.

    Refuses a structure containing null, which TOML cannot spell, and refuses one
    that is not a table, which TOML has no way to be.
    """
    save_formatted_file(data, path, schema, TOML, writer)


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
