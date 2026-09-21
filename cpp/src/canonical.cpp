#include "wrench/canonical.hpp"

#include <array>
#include <charconv>
#include <cmath>
#include <cstddef>
#include <expected>
#include <string>
#include <string_view>
#include <system_error>

#include "wrench/error.hpp"

namespace wrench {

namespace {

// Room for the longest scientific form of a double, which is 24 characters:
// a sign, seventeen significant digits, a point, and `e+308`.
constexpr std::size_t buffer_size = 32;

// A double written as `-d.dddde+xx`, taken apart.
struct parts {
    bool negative = false;
    // The significant digits with no point in them, shortest first digit last.
    std::string digits;
    // The power of ten the first digit stands at.
    int exponent = 0;
};

// std::to_chars in scientific format gives the shortest digits that read back
// as the same double, which is the half of FR-4.8 a library should not be asked
// to reproduce by hand. Fixed format would give the placement as well and is
// not usable here: it prints a large double's exact binary expansion rather
// than its shortest digits, so 1e20 comes back as 100000000000000000000 only by
// luck and 1e23 does not.
parts split(double value) {
    std::array<char, buffer_size> buffer{};
    const std::to_chars_result written = std::to_chars(buffer.data(),
                                                       buffer.data() + buffer.size(),
                                                       value,
                                                       std::chars_format::scientific);
    std::string_view text(buffer.data(), written.ptr);

    parts taken;
    taken.negative = text.starts_with('-');
    if (taken.negative) {
        text.remove_prefix(1);
    }

    const std::size_t marker = text.find('e');
    const std::string_view mantissa = text.substr(0, marker);
    std::string_view power = text.substr(marker + 1);
    // from_chars refuses a leading `+`, which to_chars always writes for a
    // non-negative exponent.
    if (power.starts_with('+')) {
        power.remove_prefix(1);
    }
    // The exponent came from to_chars, so it parses and there is nothing here
    // for a caller to handle.
    std::from_chars(power.data(), power.data() + power.size(), taken.exponent);

    taken.digits = mantissa;
    const std::size_t point = taken.digits.find('.');
    if (point != std::string::npos) {
        taken.digits.erase(point, 1);
    }
    return taken;
}

// The digits placed positionally around a decimal point, which is the whole of
// what FR-4.8 asks beyond the digits themselves.
std::string place(const parts& taken) {
    // How many digits stand before the point. One more than the exponent,
    // because the exponent is the power of the first digit.
    const int before = taken.exponent + 1;

    std::string spelled;
    if (taken.negative) {
        spelled.push_back('-');
    }
    if (before <= 0) {
        // Smaller than one, so the point leads and zeros separate it from the
        // digits. A leading zero is written rather than a bare `.5`.
        spelled += "0.";
        spelled.append(static_cast<std::size_t>(-before), '0');
        spelled += taken.digits;
    } else if (static_cast<std::size_t>(before) >= taken.digits.size()) {
        // A whole number, and it keeps its trailing `.0` so a reader can tell
        // it from an integer.
        spelled += taken.digits;
        spelled.append(static_cast<std::size_t>(before) - taken.digits.size(), '0');
        spelled += ".0";
    } else {
        spelled.append(taken.digits, 0, static_cast<std::size_t>(before));
        spelled.push_back('.');
        spelled.append(taken.digits, static_cast<std::size_t>(before));
    }
    return spelled;
}

}  // namespace

result<std::string> canonical_float(double value) {
    if (std::isnan(value)) {
        return std::unexpected(failure{.step = step::encode,
                                       .message = "a NaN has no canonical form",
                                       .cause = {}});
    }
    if (std::isinf(value)) {
        return std::unexpected(failure{.step = step::encode,
                                       .message = "an infinity has no canonical form",
                                       .cause = {}});
    }
    return place(split(value));
}

}  // namespace wrench
