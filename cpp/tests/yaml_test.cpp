// The half of YAML that is the pack's own code rather than the library's: which
// plain scalars resolve to what, and what a document that will not read reports.
//
// The tables here are derived from the type and the format rather than from
// imagination. Every spelling a value has gets a row, because a fixture set only
// agrees about the values somebody thought of, and every shape that is nearly a
// number gets one too, since that is where a resolver is wrong quietly.

#include <doctest/doctest.h>

#include <array>
#include <cmath>
#include <cstdint>
#include <jsoncons/basic_json.hpp>
#include <jsoncons/detail/make_obj_using_allocator.hpp>
#include <jsoncons/utility/read_number.hpp>
#include <span>
#include <string>
#include <string_view>

#include "wrench/codec.hpp"
#include "wrench/error.hpp"
#include "wrench/value.hpp"

namespace {

wrench::value under_v(std::string_view written) {
    const auto answer = wrench::yaml().decode("v: " + std::string(written));
    REQUIRE(answer.has_value());
    return answer->at("v");
}

// One plain scalar and what it decodes to, written as the value's own dump.
struct resolves {
    std::string_view written;
    std::string_view becomes;
};

void each(std::span<const resolves> cases) {
    for (const resolves& one : cases) {
        CAPTURE(one.written);
        CHECK(under_v(one.written).to_string() == one.becomes);
    }
}

}  // namespace

// COVERS: FR-2.9 | edge
TEST_CASE("every spelling of nothing is null") {
    static const std::array<resolves, 5> cases = {{
        {.written = "null", .becomes = "null"},
        {.written = "Null", .becomes = "null"},
        {.written = "NULL", .becomes = "null"},
        {.written = "~", .becomes = "null"},
        {.written = "", .becomes = "null"},
    }};
    each(cases);
}

// COVERS: FR-2.9 | edge
TEST_CASE("every spelling of a boolean is a boolean and no other word is") {
    static const std::array<resolves, 9> cases = {{
        {.written = "true", .becomes = "true"},
        {.written = "True", .becomes = "true"},
        {.written = "TRUE", .becomes = "true"},
        {.written = "false", .becomes = "false"},
        {.written = "False", .becomes = "false"},
        {.written = "FALSE", .becomes = "false"},
        {.written = "tRue", .becomes = R"("tRue")"},
        {.written = "y", .becomes = R"("y")"},
        {.written = "n", .becomes = R"("n")"},
    }};
    each(cases);
}

// COVERS: FR-2.9 | edge
TEST_CASE("an integer is read in every base its prefix declares") {
    static const std::array<resolves, 12> cases = {{
        {.written = "10", .becomes = "10"},
        {.written = "+10", .becomes = "10"},
        {.written = "-10", .becomes = "-10"},
        {.written = "010", .becomes = "10"},
        {.written = "0x10", .becomes = "16"},
        {.written = "0X1f", .becomes = "31"},
        {.written = "-0x10", .becomes = "-16"},
        {.written = "0o17", .becomes = "15"},
        {.written = "0O17", .becomes = "15"},
        {.written = "1_000_000", .becomes = "1000000"},
        {.written = "0", .becomes = "0"},
        {.written = "-0", .becomes = "0"},
    }};
    each(cases);
}

// The shapes that are nearly numbers. Each is a string, and a resolver that
// reached for a conversion without checking the shape first would make several of
// them numbers.
//
// COVERS: FR-2.9 | negative
TEST_CASE("what is not a number is the string it was written as") {
    static const std::array<resolves, 15> cases = {{
        {.written = "0x", .becomes = R"("0x")"},
        {.written = "0o", .becomes = R"("0o")"},
        {.written = "0xzz", .becomes = R"("0xzz")"},
        {.written = "0o9", .becomes = R"("0o9")"},
        {.written = "1-2", .becomes = R"("1-2")"},
        {.written = "1.2.3", .becomes = R"("1.2.3")"},
        {.written = "inf", .becomes = R"("inf")"},
        {.written = "nan", .becomes = R"("nan")"},
        {.written = "infinity", .becomes = R"("infinity")"},
        {.written = "1e", .becomes = R"("1e")"},
        {.written = "1e+", .becomes = R"("1e+")"},
        {.written = "e5", .becomes = R"("e5")"},
        {.written = "-x", .becomes = R"("-x")"},
        {.written = ".", .becomes = R"(".")"},
        {.written = "10:30:00", .becomes = R"("10:30:00")"},
    }};
    each(cases);
}

// COVERS: FR-4.8 | edge
TEST_CASE("a float is read in every shape YAML spells one") {
    static const std::array<resolves, 12> cases = {{
        {.written = "1.5", .becomes = "1.5"},
        {.written = "-1.5", .becomes = "-1.5"},
        {.written = "+1.5", .becomes = "1.5"},
        {.written = "1.", .becomes = "1.0"},
        {.written = ".5", .becomes = "0.5"},
        {.written = "-.5", .becomes = "-0.5"},
        {.written = "1e3", .becomes = "1000.0"},
        {.written = "1E3", .becomes = "1000.0"},
        {.written = "1e+3", .becomes = "1000.0"},
        {.written = "1e-3", .becomes = "0.001"},
        {.written = "1.5e2", .becomes = "150.0"},
        {.written = "1_0.5", .becomes = "10.5"},
    }};
    each(cases);
}

// The infinities and NaN are values a document may carry and canonical form has
// no spelling for, so they read and then refuse on the way out.
//
// COVERS: FR-4.8 | edge
TEST_CASE("an infinity and a NaN read as themselves and then refuse to be written") {
    CHECK(std::isinf(under_v(".inf").as_double()));
    CHECK(std::isinf(under_v(".Inf").as_double()));
    CHECK(std::isinf(under_v(".INF").as_double()));
    CHECK(under_v("-.inf").as_double() < 0);
    CHECK(under_v("+.inf").as_double() > 0);
    CHECK(std::isnan(under_v(".nan").as_double()));
    CHECK(std::isnan(under_v(".NaN").as_double()));
    CHECK(std::isnan(under_v(".NAN").as_double()));

    const auto answer = wrench::yaml().decode("v: .inf\n");
    REQUIRE(answer.has_value());
    CHECK_FALSE(wrench::yaml().encode(*answer).has_value());
}

// COVERS: FR-4.10 | edge
TEST_CASE("an integer past the range widens whatever base it was written in") {
    // Seventeen hexadecimal digits, which is two to the sixty-eighth less one.
    constexpr double two_to_the_sixty_eighth = 2.9514790518e+20;
    CHECK(under_v("0xFFFFFFFFFFFFFFFFF").is_double());
    CHECK(under_v("0xFFFFFFFFFFFFFFFFF").as_double() ==
          doctest::Approx(two_to_the_sixty_eighth));
    CHECK(under_v("0o7777777777777777777777777").is_double());
    CHECK(under_v("99999999999999999999999999").is_double());
    CHECK(under_v("-99999999999999999999999999").as_double() < 0);
}

// COVERS: FR-2.9 | positive
TEST_CASE("a document may be a scalar, a sequence or a mapping at the top") {
    const auto scalar = wrench::yaml().decode("just text\n");
    REQUIRE(scalar.has_value());
    CHECK(scalar->as_string() == "just text");

    const auto list = wrench::yaml().decode("- 1\n- two\n");
    REQUIRE(list.has_value());
    CHECK(list->is_array());
    CHECK(list->size() == 2);

    const auto empty = wrench::yaml().decode("");
    REQUIRE(empty.has_value());
    CHECK(empty->is_null());
}

// COVERS: FR-4.5 | edge
TEST_CASE("an empty mapping and an empty sequence survive the round trip") {
    const auto document = wrench::yaml().decode("map: {}\nlist: []\n");
    REQUIRE(document.has_value());
    CHECK(document->at("map").is_object());
    CHECK(document->at("list").is_array());

    const auto written = wrench::yaml().encode(*document);
    REQUIRE(written.has_value());
    const auto again = wrench::yaml().decode(*written);
    REQUIRE(again.has_value());
    CHECK(*again == *document);
}

// An anchor and an alias are one value written once and used twice, so the
// structure a reader gets is the same either way.
//
// COVERS: FR-4.5 | edge
TEST_CASE("an alias decodes to the value its anchor held") {
    const auto document = wrench::yaml().decode(
        "first: &held\n  kind: one\n  count: 2\nsecond: *held\nthird: &word text\n"
        "fourth: *word\n");

    REQUIRE(document.has_value());
    CHECK(document->at("first") == document->at("second"));
    CHECK(document->at("first").at("count").as<std::int64_t>() == 2);
    CHECK(document->at("fourth").as_string() == "text");
}

// COVERS: FR-2.9 | negative
TEST_CASE("a mapping key that is a collection is refused") {
    const auto answer = wrench::yaml().decode("? [1, 2]\n: value\n");

    REQUIRE_FALSE(answer.has_value());
    CHECK(answer.error().step == wrench::step::parse);
    CHECK(answer.error().message.starts_with("a mapping key that is not a string"));
}

// COVERS: FR-2.11 | negative
TEST_CASE("a document that stops in the middle is a parse failure") {
    static const std::array<std::string_view, 5> broken = {
        "list: [1, 2",
        "map: {a: 1",
        "key: \"unterminated\n",
        "\ttab: 1\n",
        "a: 1\n b: 2\n",
    };
    for (const std::string_view one : broken) {
        CAPTURE(one);
        const auto answer = wrench::yaml().decode(one);
        REQUIRE_FALSE(answer.has_value());
        CHECK(answer.error().step == wrench::step::parse);
        CHECK(answer.error().message.find("line ") != std::string::npos);
    }
}

// A stream may carry several documents and a call answering with one value has
// nowhere to put the second, so the refusal says so rather than dropping it.
//
// COVERS: FR-2.11 | edge
TEST_CASE("a file holding more than one document is refused") {
    const auto answer = wrench::yaml().decode("---\na: 1\n---\nb: 2\n");

    REQUIRE_FALSE(answer.has_value());
    CHECK(answer.error().step == wrench::step::parse);
    CHECK(answer.error().message == "a file holds more than one document");
}

// The emitter refuses text that is not UTF-8, which is the one way a value in the
// model has no YAML spelling at all.
//
// COVERS: FR-4.9 | negative
TEST_CASE("a string that is not UTF-8 is refused by the emitter") {
    wrench::value document;
    document["broken"] = std::string("\xff\xfe");

    const auto answer = wrench::yaml().encode(document);
    REQUIRE_FALSE(answer.has_value());
    CHECK(answer.error().step == wrench::step::encode);
    CHECK_FALSE(answer.error().message.empty());
}

// COVERS: FR-4.9 | negative
TEST_CASE("a key that is not UTF-8 is refused by the emitter") {
    wrench::value document;
    document[std::string("\xff\xfe")] = 1;

    CHECK_FALSE(wrench::yaml().encode(document).has_value());
}

// COVERS: FR-4.1 | edge
TEST_CASE(
    "a nested sequence and a sequence of mappings both come back as they went in") {
    const std::string written =
        "outer:\n  - - 1\n    - 2\n  - key: value\n    list:\n      - a\n";
    const auto document = wrench::yaml().decode(written);
    REQUIRE(document.has_value());

    const auto again = wrench::yaml().encode(*document);
    REQUIRE(again.has_value());
    const auto back = wrench::yaml().decode(*again);
    REQUIRE(back.has_value());
    CHECK(*back == *document);
}
