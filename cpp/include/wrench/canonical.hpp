// Canonical form for the values a codec cannot spell for itself.
#pragma once

#include <string>

#include "wrench/error.hpp"

namespace wrench {

// The one spelling a float has, by FR-4.8.
//
// Positional decimal and never an exponent, whatever the magnitude. The digits
// are the shortest decimal string that reads back as the same double, with the
// point where it belongs. A whole number keeps a trailing `.0` and a negative
// zero keeps its sign, so a reader can tell 1 from 1.0 and -0.0 from 0.0.
//
// NaN and the infinities have no canonical form and are refused with an
// `encode` failure rather than guessed at.
//
// The output is bounded and long: 311 characters for the largest finite double
// and 326 for the smallest subnormal. That cost is the requirement's, stated
// there and accepted, because a consumer reading a number with a naive numeric
// pattern gets 1 out of `1e+06`.
[[nodiscard]] result<std::string> canonical_float(double value);

}  // namespace wrench
