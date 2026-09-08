# frozen_string_literal: true

require "json"

require_relative "errors"
require_relative "float_text"

module Wrench
  # The JSON codec: bytes to a structure, and a structure to canonical bytes.
  #
  # THE STDLIB EMITS, AND THIS DECIDES TWO THINGS. `JSON.pretty_generate` with a
  # two-space indent is already canonical form for everything except floats and
  # ordering, and that is why JSON needed no hand-written emitter in any pack:
  # `encoding/json`, `json.dumps` and `serde_json` agree once sorting and indent
  # are set. Ruby is the fourth and agrees too.
  #
  #   sort the keys       two runs over one structure must agree
  #   positional floats   FR-4.8. Ruby spells 1e20 as `1.0e+20`, which a naive
  #                       numeric pattern reads as 1
  #
  # A float is handed over as a pre-spelled fragment rather than as a Float,
  # because `JSON.generate` has no hook for how a number is written. Everything
  # else, escaping included, is the library's.
  class JSONCodec
    INDENT = "  "

    # One float, already spelled, that generates as itself.
    #
    # `to_json` is what `JSON.generate` calls, so a tiny object answering it is
    # the supported seam for a value the library would otherwise spell its own
    # way. It is two lines and writes no JSON syntax.
    class Literal
      def initialize(text) = @text = text
      def to_json(*_args) = @text
    end

    # Bytes into maps, arrays and scalars.
    def decode(data)
      text = data.is_a?(String) ? data : data.to_s
      ::JSON.parse(text)
    rescue ::JSON::JSONError => e
      raise ParseError.new("could not parse the JSON", cause: e)
    end

    # A structure into canonical bytes.
    def encode(value)
      "#{::JSON.pretty_generate(prepared(value), indent: INDENT)}\n".b
    rescue ::JSON::JSONError, ArgumentError, TypeError => e
      raise EncodeError.new("could not write canonical JSON", cause: e)
    end

    private

    # The two adapters, applied to the structure before the library sees it.
    def prepared(value)
      case value
      when Hash
        value.keys.sort_by { |key| key_name(key) }
             .to_h { |key| [key_name(key), prepared(value[key])] }
      when Array then value.map { |item| prepared(item) }
      when Float then Literal.new(FloatText.canonical(value))
      else value
      end
    end

    # A mapping key, which JSON can only spell as a string.
    def key_name(key)
      raise ArgumentError, "cannot write a #{key.class} key in canonical form" unless key.is_a?(String)

      key
    end
  end

  JSON_CODEC = JSONCodec.new
end
