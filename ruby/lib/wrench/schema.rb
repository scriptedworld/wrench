# frozen_string_literal: true

require "json_schemer"

require_relative "errors"

module Wrench
  # The schema seam: `validate(value)` applied to the DECODED structure rather
  # than to the text.
  #
  # `json_schemer` 2.5.0 is the binding, chosen in
  # `docs/DECISIONS/which-json-schema-library-each-pack-binds.md`. Each pack
  # binds its language's established implementation instead of implementing
  # JSON Schema itself, FR-5.2.
  class Schema
    attr_reader :name

    def initialize(name, compiled)
      @name = name
      @compiled = compiled
    end

    # Raise unless `value` matches. The first failure is reported with the
    # pointer to where it was, because a schema over a large document says
    # nothing useful without one.
    def validate(value)
      failure = @compiled.validate(value).first
      return if failure.nil?

      where = failure["data_pointer"].to_s
      where = "the document" if where.empty?
      raise ValidationError.new(
        "#{@name}: #{where}: #{failure.fetch("error", "does not match the schema")}"
      )
    end
  end

  # Compile a schema structure into something that can validate.
  #
  # TAKES THE DECODED SCHEMA, NOT A PATH. A schema reaches a pack as a
  # structure, whether it was shipped with the pack or read from a file by the
  # caller, so compiling takes what every source already has.
  def self.compile_schema(name, structure)
    Schema.new(name, JSONSchemer.schema(structure))
  rescue StandardError => e
    raise SchemaError.new("compiling #{name}", cause: e)
  end
end
