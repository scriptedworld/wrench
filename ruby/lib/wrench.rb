# frozen_string_literal: true

require_relative "wrench/errors"
require_relative "wrench/float_text"
require_relative "wrench/schema"
require_relative "wrench/seams"
require_relative "wrench/json_codec"
require_relative "wrench/yaml_codec"

# wrench reads, writes and validates the form of the ecosystem's structured
# files. This is the Ruby pack.
#
# THE TWO CALLS ARE THE WHOLE OF FILE HANDLING, FR-2.1:
#
#     load_formatted_file(path, schema, codec, reader) -> value
#     save_formatted_file(value, path, schema, codec, writer)
#
# Load reads, decodes, then validates. Save validates, encodes, then writes.
# Validating on the way out is not symmetry for its own sake: it stops a caller
# writing a structure wrench would refuse to read back, FR-2.4, so a file
# produced by a save always survives a load.
#
# The schema argument cannot be omitted, FR-2.2. It can be wrong, and no part of
# this library detects that, FR-2.3.
#
# TWO CODECS SHIP, YAML AND JSON. TOML was the third and is retired, FR-2.7: no
# maintained library in any of the four languages could emit its canonical form,
# and the hand-written emitters written instead wrote documents they could not
# read back.
module Wrench
  # The codecs, named rather than inferred from a filename. Choosing a parser by
  # suffix would make behaviour depend on what a file is called, and renaming a
  # file would silently change how it is read.
  YAML = YAML_CODEC
  JSON = JSON_CODEC

  module_function

  # Read `path` through `reader`, decode it with `codec`, validate the result.
  #
  # Each step's failure is its own kind, so a caller learns whether the file was
  # unreadable, unparseable or simply wrong. A codec is handed bytes and a
  # schema a structure, so neither knows which file it is working on: both raise
  # with no path and this fills it in.
  def load_formatted_file(path, schema, codec, reader)
    require_seams(schema: schema, codec: codec, io: reader)
    bytes = reader.read(path)
    value = with_path(path) { codec.decode(bytes) }
    with_path(path) { schema.validate(value) }
    value
  end

  # Validate `value`, encode it with `codec`, and put it in place through
  # `writer`.
  def save_formatted_file(value, path, schema, codec, writer)
    require_seams(schema: schema, codec: codec, io: writer)
    with_path(path) { schema.validate(value) }
    bytes = with_path(path) { codec.encode(value) }
    writer.write(path, bytes)
  end

  def load_yaml_file(path, schema, reader) = load_formatted_file(path, schema, YAML, reader)
  def save_yaml_file(value, path, schema, writer) = save_formatted_file(value, path, schema, YAML, writer)
  def load_json_file(path, schema, reader) = load_formatted_file(path, schema, JSON, reader)
  def save_json_file(value, path, schema, writer) = save_formatted_file(value, path, schema, JSON, writer)

  # A missing seam is `usage`, the kind that names no step that ran, because the
  # call was made wrongly before any file was touched.
  def require_seams(schema:, codec:, io:)
    raise UsageError, "no schema was given" if schema.nil?
    raise UsageError, "no codec was given" if codec.nil?
    raise UsageError, "no reader or writer was given" if io.nil?
  end

  # Attach the file to an error raised by something that does not know it.
  def with_path(path)
    yield
  rescue Error => e
    raise e.class.new(e.message, cause: e.cause_error, path: path)
  end
end
