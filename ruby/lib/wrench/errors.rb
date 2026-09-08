# frozen_string_literal: true

# The error family. Every failure a public entry point produces is one of these,
# carrying the underlying cause, so one rescue reaches everything wrench can
# raise and no consumer ever handles Psych::SyntaxError or JSON::ParserError.
#
# A failing call says which step failed. `step` is the vocabulary a consumer
# matches on, exposed as data rather than only as a class, because bolt writes
# one into a reason's `kind`.
#
# THESE SUBCLASS StandardError AND NOTHING NARROWER. The contract forbids
# hanging them off a language's semantic error hierarchy: a validation failure
# can be a wrong type, which `'three' is not of type 'integer'` demonstrates,
# and Ruby's TypeError and ArgumentError each exclude half of what a schema
# refuses. StandardError is Ruby's rescuable base rather than a claim about what
# went wrong, which is the same position Python's pack takes with Exception.
module Wrench
  # Anything wrench raises.
  class Error < StandardError
    # The cause underneath, or nil where wrench itself is the whole story.
    attr_reader :cause_error

    # Which file it happened to, filled in by the two calls. A codec is handed
    # bytes and a schema a structure, so neither knows which file it is working
    # on: both raise with no path and the call that knows adds it.
    attr_reader :path

    def initialize(message, cause: nil, path: nil)
      @cause_error = cause
      @path = path
      super(path ? "#{message} (#{path})" : message)
    end

    # Which step failed, as a word a consumer can match on without matching on
    # a class. Six name a step of the two calls; `usage` names none that ran.
    def step
      self.class.step
    end

    # The step word for the class, so it can be read without an instance.
    def self.step
      "handling"
    end
  end

  # The reader could not supply the bytes.
  class ReadError < Error
    def self.step = "read"
  end

  # The codec could not turn bytes into a structure.
  class ParseError < Error
    def self.step = "parse"
  end

  # The structure did not match the schema.
  #
  # A SUBCLASS OF NEITHER TypeError NOR ArgumentError, deliberately. Validation
  # spans both: a wrong type and a wrong value are the same failure here.
  class ValidationError < Error
    def self.step = "validate"
  end

  # The codec could not produce canonical bytes for the structure.
  class EncodeError < Error
    def self.step = "encode"
  end

  # The writer could not put the bytes in place.
  class WriteError < Error
    def self.step = "write"
  end

  # The schema itself could not be compiled or resolved.
  class SchemaError < Error
    def self.step = "schema"
  end

  # The call was made wrongly, before any file was touched.
  #
  # The seventh kind, and the one that sits outside the two sequences: a missing
  # schema, codec, reader or writer. Rust cannot produce it because the same
  # call does not compile there. Ruby can, so Ruby has it.
  class UsageError < Error
    def self.step = "usage"
  end

  # Every step word, in the order the contract lists them. Exposed so a consumer
  # can enumerate the vocabulary rather than restating it.
  STEPS = %w[read parse schema validate encode write usage].freeze
end
