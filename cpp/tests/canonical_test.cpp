// The float spelling, which is FR-4.8 and one of the four adapters every pack
// applies.
//
// The cases are tables, which is how the packs are held level: a table that
// differs between two suites is two packs that differ, and one that agrees is
// the shared statement of what a value spells as.
#include "wrench/canonical.hpp"

#include <doctest/doctest.h>

#include <charconv>
#include <cmath>
#include <functional>
#include <initializer_list>
#include <limits>
#include <numbers>
#include <string>
#include <string_view>
#include <system_error>
#include <vector>

#include "allocation.hpp"

namespace {

// One value and the one spelling it has.
struct spelled {
    double value;
    std::string_view text;
};

// The spelling, or a failure of the test where there is none. A case asserting
// what a float looks like should not also be asserting that it has one.
std::string spelling(double value) {
    const auto answer = wrench::canonical_float(value);
    REQUIRE(answer.has_value());
    return *answer;
}

// What the text reads back as, which is the half of FR-4.8 that cannot be
// asserted by comparing strings.
double reread(std::string_view text) {
    double back = 0;
    const auto parsed = std::from_chars(text.data(), text.data() + text.size(), back);
    REQUIRE(parsed.ec == std::errc{});
    REQUIRE(parsed.ptr == text.data() + text.size());
    return back;
}

void each(const std::vector<spelled>& cases) {
    for (const spelled& one : cases) {
        CAPTURE(one.text);
        CHECK(spelling(one.value) == one.text);
    }
}

// Values chosen from the type rather than from imagination: the ends of the
// range, the magnitudes where a library switches to an exponent, and the
// fractions whose shortest digits are not their exact expansion.
const std::vector<double>& every_shape() {
    static const std::vector<double> values = {
        0.0,
        -0.0,
        1.0,
        -1.0,
        0.5,
        0.1,
        1.0 / 3.0,
        std::numbers::pi,
        1234567.875,
        -2.5e-8,
        1e20,
        1e23,
        1e-7,
        std::numeric_limits<double>::max(),
        std::numeric_limits<double>::lowest(),
        std::numeric_limits<double>::min(),
        std::numeric_limits<double>::denorm_min(),
    };
    return values;
}

// A value whose spelling is short enough to sit inside a std::string, and one
// whose digits are not.
constexpr double short_value = 1.5;

}  // namespace

// COVERS: FR-4.8 | positive
TEST_CASE("a whole number keeps a trailing point zero") {
    static const std::vector<spelled> cases = {
        {.value = 1.0, .text = "1.0"},
        {.value = -2.0, .text = "-2.0"},
        {.value = 0.0, .text = "0.0"},
        {.value = 125.0, .text = "125.0"},
    };
    each(cases);
}

// COVERS: FR-4.8 | positive
TEST_CASE("a fraction is written positionally") {
    static const std::vector<spelled> cases = {
        {.value = 1.5, .text = "1.5"},
        {.value = 0.1, .text = "0.1"},
        {.value = -0.25, .text = "-0.25"},
        {.value = 1.0 / 3.0, .text = "0.3333333333333333"},
    };
    each(cases);
}

// COVERS: FR-4.8 | edge
TEST_CASE("a negative zero keeps its sign") {
    static const std::vector<spelled> cases = {
        {.value = -0.0, .text = "-0.0"},
        {.value = 0.0, .text = "0.0"},
    };
    each(cases);
}

// COVERS: FR-4.8 | edge
TEST_CASE("a magnitude that would take an exponent takes none") {
    static const std::vector<spelled> cases = {
        {.value = 1e20, .text = "100000000000000000000.0"},
        {.value = 1e-7, .text = "0.0000001"},
        {.value = -1e-7, .text = "-0.0000001"},
    };
    each(cases);
}

// The digits are the shortest that read back as the same double, not the
// value's exact binary expansion. 1e23 is the case that tells the two apart:
// the nearest double is 99999999999999991611392, and that is what a fixed
// format prints.

// COVERS: FR-4.8 | edge
TEST_CASE("the digits are the shortest that read back, not the exact expansion") {
    static const std::vector<spelled> cases = {
        {.value = 1e23, .text = "100000000000000000000000.0"},
        {.value = 0.1, .text = "0.1"},
    };
    each(cases);
}

// COVERS: FR-4.8 | edge
TEST_CASE("the longest spellings are the ones the requirement states") {
    const std::string largest = spelling(std::numeric_limits<double>::max());
    CHECK(largest.size() == 311);
    CHECK(largest.starts_with("17976931348623157"));
    CHECK(largest.ends_with(".0"));

    const std::string smallest = spelling(std::numeric_limits<double>::denorm_min());
    CHECK(smallest.size() == 326);
    CHECK(smallest.starts_with("0.0"));
    CHECK(smallest.ends_with("5"));
}

// COVERS: FR-4.8 | property
TEST_CASE("no spelling carries an exponent") {
    for (const double value : every_shape()) {
        const std::string text = spelling(value);
        CAPTURE(text);
        CHECK(text.find('e') == std::string::npos);
        CHECK(text.find('E') == std::string::npos);
        CHECK(text.find('.') != std::string::npos);
    }
}

// COVERS: FR-4.8 | property
TEST_CASE("every spelling reads back as the value it came from") {
    for (const double value : every_shape()) {
        const std::string text = spelling(value);
        CAPTURE(text);
        const double back = reread(text);
        CHECK(back == value);
        CHECK(std::signbit(back) == std::signbit(value));
    }
}

// COVERS: FR-4.8 | negative
TEST_CASE("a NaN is refused") {
    const auto answer =
        wrench::canonical_float(std::numeric_limits<double>::quiet_NaN());
    REQUIRE_FALSE(answer.has_value());
    CHECK(answer.error().step == wrench::step::encode);
    CHECK(answer.error().message == "a NaN has no canonical form");
    CHECK_FALSE(static_cast<bool>(answer.error().cause));
}

// COVERS: FR-4.8 | negative
TEST_CASE("both infinities are refused") {
    const double infinity = std::numeric_limits<double>::infinity();
    for (const double value : {infinity, -infinity}) {
        const auto answer = wrench::canonical_float(value);
        REQUIRE_FALSE(answer.has_value());
        CHECK(answer.error().step == wrench::step::encode);
        CHECK(answer.error().message == "an infinity has no canonical form");
    }
}

// An allocation failure leaves as std::bad_alloc rather than as a failure,
// because reporting one would mean building a message, which allocates. The
// sweep is what takes the throwing edge of every allocating call in the
// spelling, and gcov counts each of those as a branch.
//
// Nothing inside a swept body asserts. An assertion allocates, and the body
// runs with an allocation armed to fail.

// COVERS: FR-4.8 | edge
TEST_CASE("a spelling short enough to sit in the string itself allocates nothing") {
    const wrench::test::sweep found = wrench::test::fail_each_allocation(
        [] { const auto answer = wrench::canonical_float(short_value); });
    CHECK(found.completed);
    CHECK(found.thrown == 0);
    CHECK(found.absorbed == 0);
}

// Seventeen significant digits are more than a std::string holds inside itself,
// so taking the value apart allocates as well as spelling it does. That is the
// case that reaches the throwing edge of the first half.

// COVERS: FR-4.8 | edge
TEST_CASE("a value with the most digits throws wherever it cannot allocate") {
    const wrench::test::sweep found = wrench::test::fail_each_allocation([] {
        const auto answer = wrench::canonical_float(std::numeric_limits<double>::max());
    });
    CHECK(found.completed);
    CHECK(found.thrown > 1);
    CHECK(found.absorbed == 0);
}

// COVERS: FR-4.8 | edge
TEST_CASE("the longest spelling throws at every allocation it makes") {
    const wrench::test::sweep found = wrench::test::fail_each_allocation([] {
        const auto answer =
            wrench::canonical_float(std::numeric_limits<double>::denorm_min());
    });
    CHECK(found.completed);
    CHECK(found.thrown > 0);
    CHECK(found.absorbed == 0);
}
