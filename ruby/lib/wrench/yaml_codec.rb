# frozen_string_literal: true

require "psych"

require_relative "errors"
require_relative "float_text"

module Wrench
  # The YAML codec: bytes to a structure, and a structure to canonical bytes.
  #
  # PSYCH EMITS, AND THIS DECIDES FOUR THINGS. The document is built as a tree of
  # `Psych::Nodes` with the style named on each scalar, and Psych turns that into
  # text. Nothing here writes a character of YAML: layout, indentation, escaping
  # and line breaks are all Psych's, and its escape table is the one that ships.
  #
  # The four are the adapters `packs-agree-on-structure-not-on-bytes` names, and
  # they exist because they preserve MEANING rather than layout:
  #
  #   sort the keys                two runs over one structure must agree
  #   quote every string and key   `no`, `1.20`, `null` and `10` stay what they
  #                                were. The key is the sharp one: to a YAML 1.1
  #                                reader an unquoted `10:` is an integer key
  #   positional floats            FR-4.8, and `1e+20` read by a naive numeric
  #                                pattern yields 1
  #   null written as the word     an empty value and a missing one should not
  #                                look the same to a reader
  #
  # Psych writes block sequences without indenting them under their key. That is
  # its choice and it is left alone: packs agree on structure now, so a sibling
  # pack's different whitespace is not a defect.
  class YAMLCodec
    # Bytes into maps, arrays and scalars.
    #
    # `Psych::Exception` does not cross this boundary; the cause is kept.
    # Aliases are refused rather than expanded, because a document that expands
    # to something larger than itself is a denial of service in a library whose
    # whole job is reading files from elsewhere.
    def decode(data)
      text = data.is_a?(String) ? data.dup.force_encoding("UTF-8") : data.to_s
      Psych.safe_load(text, permitted_classes: [], aliases: false)
    rescue Psych::Exception, ArgumentError => e
      raise ParseError.new("could not parse the YAML", cause: e)
    end

    # A structure into canonical bytes.
    def encode(value)
      document = Psych::Nodes::Document.new([], [], true)
      document.children << node(value)
      stream = Psych::Nodes::Stream.new
      stream.children << document
      stream.to_yaml.b
    rescue ArgumentError, TypeError => e
      raise EncodeError.new("could not write canonical YAML", cause: e)
    end

    private

    # One value as a Psych node, with the style this codec wants on it.
    def node(value)
      case value
      when Hash  then mapping(value)
      when Array then sequence(value)
      else scalar(value)
      end
    end

    # Adapter one: keys sorted. A mapping has no order of its own, so sorting is
    # what makes two runs over the same structure produce the same bytes.
    def mapping(value)
      out = Psych::Nodes::Mapping.new(nil, nil, true, Psych::Nodes::Mapping::BLOCK)
      value.keys.sort_by { |key| key_name(key) }.each do |key|
        out.children << scalar(key_name(key))
        out.children << node(value[key])
      end
      out
    end

    def sequence(value)
      out = Psych::Nodes::Sequence.new(nil, nil, true, Psych::Nodes::Sequence::BLOCK)
      value.each { |item| out.children << node(item) }
      out
    end

    # A mapping key, which JSON Schema and every pack can only spell as a
    # string. Refused rather than written otherwise: Ruby's Hash takes any
    # object, and a bare `1:` would emit a document this codec's own decoder
    # then reads as an integer key. Go and Rust cannot reach this, their map
    # keys being strings by type.
    def key_name(name)
      raise ArgumentError, "cannot write a #{name.class} key in canonical form" unless name.is_a?(String)

      name
    end

    # Adapters two, three and four. A string is double quoted and everything
    # else is plain, which is what keeps a type through a round trip.
    # Psych wants the style AND the two flags that agree with it: `plain` and
    # `quoted` are what its emitter checks, and setting only the style raises
    # `neither tag nor implicit flags are specified`.
    def scalar(value)
      text, style = spelling(value)
      plain = style == PLAIN
      Psych::Nodes::Scalar.new(text, nil, nil, plain, !plain, style)
    end

    PLAIN = Psych::Nodes::Scalar::PLAIN
    QUOTED = Psych::Nodes::Scalar::DOUBLE_QUOTED

    def spelling(value)
      case value
      when nil         then ["null", PLAIN]
      when true, false then [value.to_s, PLAIN]
      when Integer     then [value.to_s, PLAIN]
      when Float       then [FloatText.canonical(value), PLAIN]
      when String      then [value, QUOTED]
      else raise ArgumentError, "cannot write #{value.class} in canonical form"
      end
    end
  end

  YAML_CODEC = YAMLCodec.new
end
