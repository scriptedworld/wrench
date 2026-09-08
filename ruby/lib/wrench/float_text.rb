# frozen_string_literal: true

require "bigdecimal"

module Wrench
  # The one spelling of a float, shared by all three of this pack's codecs.
  #
  # FR-4.8. Positional decimal, never an exponent. The digits are the shortest
  # decimal string that reads back as the same float, placed with the decimal
  # point where it belongs rather than moved into an `e`. A whole number keeps a
  # `.0`, so a float never reads back as an integer.
  #
  # The rule carries no threshold on purpose. Every alternative needs a
  # magnitude at which the spelling changes, and that number then has to be
  # stated in the contract and implemented identically in every pack. "Never" is
  # the only answer with nothing to get wrong, and the only one a consumer
  # parsing with a naive numeric pattern reads correctly: `1e+06` matched by
  # `[0-9.]+` yields 1, which is how this defect was found.
  module FloatText
    module_function

    # The canonical spelling of one float.
    #
    # Ruby's `Float#to_s` gives the shortest round-tripping digits and chooses
    # an exponent on a threshold of its own, exactly as Python's `repr` does.
    # BigDecimal of that string is exact, and `to_s("F")` places the point
    # positionally without touching the digits, so the round trip is Ruby's and
    # only the placement is wrench's.
    #
    # NaN and the infinities are refused. YAML can spell them, JSON Schema
    # cannot represent them, and a file no consumer in this ecosystem can
    # validate is not canonical form.
    def canonical(value)
      raise ArgumentError, "cannot write #{value} in canonical form" if value.nan? || value.infinite?

      text = BigDecimal(value.to_s).to_s("F")
      # BigDecimal renders a whole number as "1.0" already, so the point is
      # always there. Trailing zeros past the significant digits are not: "1.20"
      # is the float 1.2 and has to spell itself that way, which is the
      # complement the contract warns about.
      text = text.sub(/(\.\d*?[1-9])0+\z/, '\1').sub(/\.0+\z/, ".0")
      text
    end
  end
end
