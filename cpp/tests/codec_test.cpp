// The two codecs: what they decode to, what they emit, and what they refuse.
//
// The cases are tables, which is how the packs are held level: a table that
// differs between two suites is two packs that differ, and one that agrees is the
// shared statement of what a document means.

#include "wrench/codec.hpp"

#include <doctest/doctest.h>

#include <cmath>
#include <cstdint>
#include <format>
#include <jsoncons/basic_json.hpp>
#include <jsoncons/semantic_tag.hpp>
#include <jsoncons/utility/read_number.hpp>
#include <limits>
#include <string>
#include <string_view>
#include <vector>

#include "wrench/error.hpp"
#include "wrench/value.hpp"

namespace {

// The value, or a failure of the test where there is none. A case asserting what
// a document decodes to should not also be asserting that it decodes.
wrench::value decoded(const wrench::codec& format, std::string_view bytes) {
    const auto answer = format.decode(bytes);
    REQUIRE(answer.has_value());
    return *answer;
}

std::string encoded(const wrench::codec& format, const wrench::value& document) {
    const auto answer = format.encode(document);
    REQUIRE(answer.has_value());
    return *answer;
}

// One plain scalar and the type and spelling it resolves to, written as the
// decoded document's own dump so the case reads as one line.
struct resolves {
    std::string_view written;
    std::string_view becomes;
};

void each(const std::vector<resolves>& cases) {
    for (const resolves& one : cases) {
        CAPTURE(one.written);
        const wrench::value document =
            decoded(wrench::yaml(), "v: " + std::string(one.written));
        CHECK(document.at("v").to_string() == one.becomes);
    }
}

}  // namespace

// COVERS: FR-2.7 | positive
TEST_CASE("two codecs ship and each reads what it wrote") {
    const wrench::value document =
        decoded(wrench::yaml(), "name: build\ncount: 3\nready: true\n");

    CHECK(decoded(wrench::yaml(), encoded(wrench::yaml(), document)) == document);
    CHECK(decoded(wrench::json(), encoded(wrench::json(), document)) == document);
}

// COVERS: FR-2.9 | property
TEST_CASE("a decoder produces maps, lists and the JSON scalars and nothing else") {
    const wrench::value document = decoded(
        wrench::yaml(), "when: 2026-01-01\nat: 12:30\nlist:\n  - 1\nmap:\n  a: b\n");

    CHECK(document.at("when").is_string());
    CHECK(document.at("when").as_string() == "2026-01-01");
    CHECK(document.at("at").is_string());
    CHECK(document.at("list").is_array());
    CHECK(document.at("map").is_object());
    CHECK(document.at("map").at("a").is_string());
}

// COVERS: FR-2.9 | negative
TEST_CASE("a mapping key that is not a string is refused rather than stringified") {
    const auto answer = wrench::yaml().decode("10: ok\n");

    REQUIRE_FALSE(answer.has_value());
    CHECK(answer.error().step == wrench::step::parse);
    CHECK(answer.error().message.starts_with(
        "a mapping key that is not a string is refused"));
}

// COVERS: FR-2.9 | edge
TEST_CASE("a quoted key that looks like a number is a string and is kept") {
    const wrench::value document = decoded(wrench::yaml(), "\"10\": ok\n");

    CHECK(document.at("10").as_string() == "ok");
}

// The table the pack resolves a plain scalar by, measured against what the other
// packs decode rather than taken from a YAML version number.
//
// COVERS: FR-2.9 | positive
TEST_CASE("a plain scalar resolves by the shared table") {
    static const std::vector<resolves> cases = {
        {.written = "no", .becomes = R"("no")"},
        {.written = "yes", .becomes = R"("yes")"},
        {.written = "on", .becomes = R"("on")"},
        {.written = "off", .becomes = R"("off")"},
        {.written = "null", .becomes = "null"},
        {.written = "~", .becomes = "null"},
        {.written = "true", .becomes = "true"},
        {.written = "false", .becomes = "false"},
        {.written = "10", .becomes = "10"},
        {.written = "010", .becomes = "10"},
        {.written = "0x10", .becomes = "16"},
        {.written = "1_000", .becomes = "1000"},
        {.written = "2026-01-01", .becomes = R"("2026-01-01")"},
        {.written = "12:30", .becomes = R"("12:30")"},
    };
    each(cases);
}

// COVERS: FR-2.9 | edge
TEST_CASE("an empty value and a missing one are both null") {
    const wrench::value document = decoded(wrench::yaml(), "empty:\nalso: null\n");

    CHECK(document.at("empty").is_null());
    CHECK(document.at("also").is_null());
}

// COVERS: FR-4.2 | positive
TEST_CASE("a quoted string survives the round trip as the string it was") {
    const wrench::value document = decoded(
        wrench::yaml(), "answer: \"no\"\nversion: \"1.20\"\nabsent: \"null\"\n");

    CHECK(document.at("answer").as_string() == "no");
    CHECK(document.at("version").as_string() == "1.20");
    CHECK(document.at("absent").as_string() == "null");
    CHECK(encoded(wrench::yaml(), document) ==
          "\"absent\": \"null\"\n\"answer\": \"no\"\n\"version\": \"1.20\"\n");
}

// The surprising half: an unquoted 1.20 was a number, and that number has no
// trailing zero.
//
// COVERS: FR-4.2 | edge
TEST_CASE("an unquoted version number comes back with its trailing zero gone") {
    const wrench::value document = decoded(wrench::yaml(), "version: 1.20\n");

    CHECK(document.at("version").is_double());
    CHECK(encoded(wrench::yaml(), document) == "\"version\": 1.2\n");
}

// COVERS: FR-4.1 | property
TEST_CASE("a scalar is quoted exactly when it is a string") {
    const wrench::value document =
        decoded(wrench::yaml(),
                "count: 3\nname: build\nnothing: null\nratio: 0.5\nyes_no: true\n");

    CHECK(encoded(wrench::yaml(), document) ==
          "\"count\": 3\n"
          "\"name\": \"build\"\n"
          "\"nothing\": null\n"
          "\"ratio\": 0.5\n"
          "\"yes_no\": true\n");
}

// COVERS: FR-4.4 | positive
TEST_CASE("flow style comes back as block style") {
    const wrench::value document =
        decoded(wrench::yaml(), "tools: [go, gofmt]\nlimits: {cpu: 2}\n");

    CHECK(encoded(wrench::yaml(), document) ==
          "\"limits\":\n"
          "  \"cpu\": 2\n"
          "\"tools\":\n"
          "- \"go\"\n"
          "- \"gofmt\"\n");
}

// COVERS: FR-4.1 | negative
TEST_CASE("a value with no canonical form is refused rather than guessed at") {
    wrench::value document;
    document["broken"] = std::numeric_limits<double>::quiet_NaN();

    const auto yaml = wrench::yaml().encode(document);
    REQUIRE_FALSE(yaml.has_value());
    CHECK(yaml.error().step == wrench::step::encode);
    CHECK(yaml.error().message == "a NaN has no canonical form");

    const auto json = wrench::json().encode(document);
    REQUIRE_FALSE(json.has_value());
    CHECK(json.error().step == wrench::step::encode);
}

// COVERS: FR-4.1 | edge
TEST_CASE("an infinity is refused in both codecs") {
    wrench::value document;
    document["far"] = std::numeric_limits<double>::infinity();

    CHECK_FALSE(wrench::yaml().encode(document).has_value());
    CHECK_FALSE(wrench::json().encode(document).has_value());
}

// A library's own tagged kinds are not the value model. A decimal carried as a
// tagged string would be written unquoted, which is bytes the value never said.
//
// COVERS: FR-2.9 | negative
TEST_CASE("a value outside the model is refused by both codecs") {
    wrench::value document;
    document["raw"] = wrench::value("1e9", jsoncons::semantic_tag::bigdec);

    const auto json = wrench::json().encode(document);
    REQUIRE_FALSE(json.has_value());
    CHECK(json.error().step == wrench::step::encode);
    CHECK(json.error().message.starts_with("a value outside the model"));

    CHECK_FALSE(wrench::yaml().encode(document).has_value());
}

// COVERS: FR-4.5 | property
TEST_CASE("a structure saved and read back is the structure that went in") {
    const wrench::value document = decoded(
        wrench::yaml(),
        "reasons:\n  - kind: one\n    files: [a, b]\n  - kind: two\nsuccess: false\n");

    CHECK(decoded(wrench::yaml(), encoded(wrench::yaml(), document)) == document);
    CHECK(decoded(wrench::json(), encoded(wrench::json(), document)) == document);
}

// COVERS: FR-4.6 | positive
TEST_CASE("JSON is two-space indented with sorted keys and a trailing newline") {
    const wrench::value document =
        decoded(wrench::yaml(), "zebra: 1\nalpha:\n  - one\n  - two\n");

    CHECK(encoded(wrench::json(), document) ==
          "{\n"
          "  \"alpha\": [\n"
          "    \"one\",\n"
          "    \"two\"\n"
          "  ],\n"
          "  \"zebra\": 1\n"
          "}\n");
}

// COVERS: FR-4.6 | edge
TEST_CASE("a short object is not collapsed onto one line") {
    const wrench::value document = decoded(wrench::json(), R"({"a": {"b": 1}})");

    CHECK(encoded(wrench::json(), document) == "{\n  \"a\": {\n    \"b\": 1\n  }\n}\n");
}

// COVERS: FR-4.9 | positive
TEST_CASE("a control character is escaped by the format's own table") {
    const wrench::value document = decoded(
        wrench::yaml(), "nul: \"\\x00\"\nescape: \"\\x1b\"\nline_sep: \"\\u2028\"\n");

    CHECK(encoded(wrench::yaml(), document) ==
          "\"escape\": \"\\e\"\n\"line_sep\": \"\\L\"\n\"nul\": \"\\0\"\n");
}

// COVERS: FR-4.9 | edge
TEST_CASE("no value is refused for carrying a control character") {
    const wrench::value document = decoded(wrench::yaml(), "bell: \"\\a\"\n");

    CHECK(document.at("bell").as_string() == std::string(1, '\a'));
    CHECK(wrench::json().encode(document).has_value());
}

// COVERS: FR-4.10 | edge
TEST_CASE("an integer past the signed 64-bit range widens to a float, visibly") {
    const std::string written =
        "within_max: 9223372036854775807\n"
        "past_max: 9223372036854775808\n"
        "uint64_max: 18446744073709551615\n"
        "past_uint64: 18446744073709551616\n";

    CHECK(encoded(wrench::yaml(), decoded(wrench::yaml(), written)) ==
          "\"past_max\": 9223372036854776000.0\n"
          "\"past_uint64\": 18446744073709552000.0\n"
          "\"uint64_max\": 18446744073709552000.0\n"
          "\"within_max\": 9223372036854775807\n");
}

// COVERS: FR-4.10 | property
TEST_CASE("the same integers widen the same way in both codecs") {
    const std::string written =
        R"({"within_min": -9223372036854775808, "past_min": -9223372036854775809,)"
        R"( "far": 1000000000000000000000})";
    const wrench::value document = decoded(wrench::json(), written);

    CHECK(document.at("within_min").as<std::int64_t>() ==
          std::numeric_limits<std::int64_t>::min());
    CHECK(document.at("past_min").is_double());
    CHECK(document.at("far").is_double());
    CHECK(
        encoded(wrench::json(), document) ==
        encoded(
            wrench::json(),
            decoded(wrench::yaml(),
                    "within_min: -9223372036854775808\npast_min: -9223372036854775809\n"
                    "far: 1000000000000000000000\n")));
}

// COVERS: FR-4.11 | edge
TEST_CASE("negative zero is a value in JSON and a spelling in YAML") {
    const wrench::value from_json = decoded(wrench::json(), R"({"a": -0, "b": -0.0})");
    CHECK(from_json.at("a").is_double());
    CHECK(std::signbit(from_json.at("a").as_double()));
    CHECK(std::signbit(from_json.at("b").as_double()));

    const wrench::value from_yaml = decoded(wrench::yaml(), "a: -0\nb: -0.0\n");
    CHECK_FALSE(from_yaml.at("a").is_double());
    CHECK(from_yaml.at("a").as<std::int64_t>() == 0);
    CHECK(std::signbit(from_yaml.at("b").as_double()));
}

// COVERS: FR-4.11 | regression
TEST_CASE("a hyphen and a zero inside a string are not a number token") {
    const wrench::value document = decoded(wrench::json(), R"({"a-0": "-0", "b": -0})");

    CHECK(document.at("a-0").as_string() == "-0");
    CHECK(document.at("b").is_double());
    CHECK(encoded(wrench::json(), document) ==
          "{\n  \"a-0\": \"-0\",\n  \"b\": -0.0\n}\n");
}

// COVERS: FR-2.11 | negative
TEST_CASE("a document that will not parse is a parse failure naming where") {
    const auto yaml = wrench::yaml().decode("a: b: c\n");
    REQUIRE_FALSE(yaml.has_value());
    CHECK(yaml.error().step == wrench::step::parse);
    CHECK(yaml.error().message.find("line 1") != std::string::npos);

    const auto json = wrench::json().decode("{\"a\": }");
    REQUIRE_FALSE(json.has_value());
    CHECK(json.error().step == wrench::step::parse);
    CHECK_FALSE(json.error().message.empty());
}

// COVERS: FR-2.11 | property
TEST_CASE("the step vocabulary is data and every kind has its word") {
    CHECK(wrench::name(wrench::step::read) == "read");
    CHECK(wrench::name(wrench::step::parse) == "parse");
    CHECK(wrench::name(wrench::step::schema) == "schema");
    CHECK(wrench::name(wrench::step::validate) == "validate");
    CHECK(wrench::name(wrench::step::encode) == "encode");
    CHECK(wrench::name(wrench::step::write) == "write");
}
