// The two calls and the four wrappers: the order of the steps, which step a
// failure names, and what reaches the file.

#include "wrench/file.hpp"

#include <doctest/doctest.h>

#include <filesystem>
#include <initializer_list>
#include <jsoncons/basic_json.hpp>
#include <jsoncons/utility/read_number.hpp>
#include <limits>
#include <string>
#include <string_view>

#include "support.hpp"
#include "wrench/codec.hpp"
#include "wrench/error.hpp"
#include "wrench/io.hpp"
#include "wrench/schema.hpp"
#include "wrench/value.hpp"

namespace {

// A reader answering from memory, so a load is exercised against no filesystem
// at all (FR-2.5a).
class canned final : public wrench::reader {
   public:
    explicit canned(std::string_view bytes) : bytes_(bytes) {}

    [[nodiscard]] wrench::result<std::string> read(
        const std::filesystem::path& /*path*/) const override {
        return bytes_;
    }

   private:
    std::string bytes_;
};

wrench::value parsed(std::string_view text) {
    const auto answer = wrench::json().decode(text);
    REQUIRE(answer.has_value());
    return *answer;
}

wrench::schema anything() {
    auto answer = wrench::schema::compile(parsed(R"({"type": "object"})"));
    REQUIRE(answer.has_value());
    return *answer;
}

constexpr std::string_view an_envelope = "success: true\n";

}  // namespace

// COVERS: FR-2.1 | positive
TEST_CASE("file handling is two calls and what one writes the other reads") {
    const wrench::test::scratch area;
    const std::filesystem::path file = area.at("envelope.yaml");
    const wrench::local_file disk;
    const wrench::value document = parsed(R"({"success": true})");

    const auto saved = wrench::save_formatted_file(
        document, file, wrench::schemas::envelope(), wrench::yaml(), disk);
    REQUIRE(saved.has_value());

    const auto loaded = wrench::load_formatted_file(
        file, wrench::schemas::envelope(), wrench::yaml(), disk);
    REQUIRE(loaded.has_value());
    CHECK(*loaded == document);
}

// COVERS: FR-4.3 | positive
TEST_CASE("canonical form belongs to the save call") {
    const wrench::test::scratch area;
    const std::filesystem::path file = area.at("jig.yaml");
    wrench::value document;
    document["zebra"] = 1;
    document["alpha"] = 1.0;

    REQUIRE(wrench::save_yaml_file(document, file, anything(), wrench::local_file())
                .has_value());

    CHECK(wrench::test::slurp(file) == "\"alpha\": 1.0\n\"zebra\": 1\n");
}

// COVERS: FR-2.2 | positive
TEST_CASE("nothing is read without naming what the file must conform to") {
    const canned source(an_envelope);
    const auto answer = wrench::load_formatted_file(
        "envelope.yaml", wrench::schemas::jig(), wrench::yaml(), source);

    REQUIRE_FALSE(answer.has_value());
    CHECK(answer.error().step == wrench::step::validate);
}

// The signature compels a schema and cannot compel the right one. A document
// that happens to satisfy the schema it was handed is loaded, however little
// that schema has to do with what the file is.
//
// COVERS: FR-2.3 | edge
TEST_CASE("the wrong schema is not detected") {
    const canned source(an_envelope);
    const auto answer = wrench::load_formatted_file(
        "envelope.yaml", wrench::schemas::definitions(), wrench::yaml(), source);

    CHECK(answer.has_value());
}

// COVERS: FR-2.4 | negative
TEST_CASE("a structure wrench would refuse to read back is never written") {
    const wrench::test::scratch area;
    const std::filesystem::path file = area.at("refused.yaml");
    const wrench::value document = parsed(R"({"success": false})");

    const auto saved = wrench::save_yaml_file(
        document, file, wrench::schemas::envelope(), wrench::local_file());

    REQUIRE_FALSE(saved.has_value());
    CHECK(saved.error().step == wrench::step::validate);
    CHECK_FALSE(std::filesystem::exists(file));
}

// COVERS: FR-2.6 | negative
TEST_CASE("a load names the step that failed and the file it was reading") {
    const wrench::test::scratch area;

    SUBCASE("the reader could not supply the bytes") {
        const auto answer = wrench::load_yaml_file(
            area.at("absent.yaml"), anything(), wrench::local_file());
        REQUIRE_FALSE(answer.has_value());
        CHECK(answer.error().step == wrench::step::read);
        CHECK(answer.error().message.starts_with("reading "));
    }

    SUBCASE("the codec could not turn the bytes into a structure") {
        const canned source("a: b: c\n");
        const auto answer = wrench::load_yaml_file("broken.yaml", anything(), source);
        REQUIRE_FALSE(answer.has_value());
        CHECK(answer.error().step == wrench::step::parse);
        CHECK(answer.error().message.starts_with("parsing broken.yaml: "));
    }

    SUBCASE("the structure did not match the schema") {
        const canned source("success: 1\n");
        const auto answer = wrench::load_yaml_file(
            "envelope.yaml", wrench::schemas::envelope(), source);
        REQUIRE_FALSE(answer.has_value());
        CHECK(answer.error().step == wrench::step::validate);
        CHECK(answer.error().message.starts_with("validating envelope.yaml: /success"));
    }

    SUBCASE("the schema itself was never compiled") {
        const canned source(an_envelope);
        const auto answer =
            wrench::load_yaml_file("envelope.yaml", wrench::schema(), source);
        REQUIRE_FALSE(answer.has_value());
        CHECK(answer.error().step == wrench::step::schema);
        CHECK(answer.error().message ==
              "the schema for envelope.yaml: no schema was compiled");
    }
}

// COVERS: FR-2.6 | negative
TEST_CASE("a save names the step that failed and the file it was writing") {
    const wrench::test::scratch area;

    SUBCASE("the codec could not produce canonical bytes") {
        wrench::value document;
        document["ratio"] = std::numeric_limits<double>::quiet_NaN();
        const auto answer = wrench::save_json_file(
            document, area.at("nan.json"), anything(), wrench::local_file());
        REQUIRE_FALSE(answer.has_value());
        CHECK(answer.error().step == wrench::step::encode);
        CHECK(answer.error().message == "encoding " + area.at("nan.json").string() +
                                            ": a NaN has no canonical form");
    }

    SUBCASE("the writer could not put the bytes in place") {
        const auto answer = wrench::save_json_file(parsed("{}"),
                                                   area.at("absent/deeper.json"),
                                                   anything(),
                                                   wrench::local_file());
        REQUIRE_FALSE(answer.has_value());
        CHECK(answer.error().step == wrench::step::write);
        CHECK(answer.error().message.starts_with("writing "));
    }
}

// The path is filled in by the two calls, because a codec is handed bytes and a
// schema a structure and neither knows which file it is working on.
//
// COVERS: FR-2.11 | property
TEST_CASE("every failure the calls produce carries the file and the kind") {
    const canned source("a: b: c\n");
    const auto answer = wrench::load_json_file("named.json", anything(), source);

    REQUIRE_FALSE(answer.has_value());
    CHECK(wrench::name(answer.error().step) == "parse");
    CHECK(answer.error().message.find("named.json") != std::string::npos);
    // The cause is the library's, and it travels in the message rather than as a
    // type a consumer would have to link against.
    CHECK(answer.error().message.size() > std::string("parsing named.json: ").size());
}

// COVERS: FR-2.10 | positive
TEST_CASE("each wrapper supplies its codec and adds nothing else") {
    const wrench::test::scratch area;
    const wrench::local_file disk;
    const wrench::value document = parsed(R"({"success": true})");
    const std::filesystem::path as_yaml = area.at("through.yaml");
    const std::filesystem::path as_json = area.at("through.json");

    REQUIRE(wrench::save_yaml_file(document, as_yaml, anything(), disk).has_value());
    REQUIRE(wrench::save_json_file(document, as_json, anything(), disk).has_value());

    CHECK(wrench::test::slurp(as_yaml) == "\"success\": true\n");
    CHECK(wrench::test::slurp(as_json) == "{\n  \"success\": true\n}\n");

    const auto from_yaml = wrench::load_yaml_file(as_yaml, anything(), disk);
    const auto from_json = wrench::load_json_file(as_json, anything(), disk);
    REQUIRE(from_yaml.has_value());
    REQUIRE(from_json.has_value());
    CHECK(*from_yaml == *from_json);
}

// COVERS: FR-2.10 | property
TEST_CASE("a wrapper and the core call naming the same codec answer alike") {
    const canned source(an_envelope);
    const auto through_wrapper =
        wrench::load_yaml_file("envelope.yaml", wrench::schemas::envelope(), source);
    const auto through_core = wrench::load_formatted_file(
        "envelope.yaml", wrench::schemas::envelope(), wrench::yaml(), source);

    REQUIRE(through_wrapper.has_value());
    REQUIRE(through_core.has_value());
    CHECK(*through_wrapper == *through_core);
}

// COVERS: FR-2.5a | positive
TEST_CASE("a substituted reader exercises the validation paths against no filesystem") {
    const canned source("success: 1\n");
    const auto answer =
        wrench::load_yaml_file("nowhere.yaml", wrench::schemas::envelope(), source);

    REQUIRE_FALSE(answer.has_value());
    CHECK(answer.error().step == wrench::step::validate);
}

// COVERS: FR-4.5 | property
TEST_CASE("a file saved and loaded back yields the structure that went in") {
    const wrench::test::scratch area;
    const wrench::local_file disk;
    const wrench::value document = parsed(
        R"({"success": false, "reasons": [{"kind": "tool", "message": "3 files"}],
            "metadata": {"statistics": {"checked": 12}, "evidence": ["work/out"]}})");

    struct through {
        std::string_view name;
        const wrench::codec* format;
    };
    for (const through& one :
         {through{.name = "round.yaml", .format = &wrench::yaml()},
          through{.name = "round.json", .format = &wrench::json()}}) {
        CAPTURE(one.name);
        const std::filesystem::path file = area.at(one.name);
        REQUIRE(wrench::save_formatted_file(
                    document, file, wrench::schemas::envelope(), *one.format, disk)
                    .has_value());
        const auto loaded = wrench::load_formatted_file(
            file, wrench::schemas::envelope(), *one.format, disk);
        REQUIRE(loaded.has_value());
        CHECK(*loaded == document);
    }
}
