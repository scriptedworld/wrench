// The validate seam and the shipped set: what resolves, what is refused, and
// that what the pack carries is the bytes in `schemas/` rather than a copy.
//
// The directory and the fixture set are read here rather than restated, so a
// schema added to `schemas/` shows up as a failing case in this file and nowhere
// else has to be remembered.

#include "wrench/schema.hpp"

#include <doctest/doctest.h>

#include <algorithm>
#include <cstddef>
#include <filesystem>
#include <initializer_list>
#include <jsoncons/basic_json.hpp>
#include <jsoncons/utility/read_number.hpp>
#include <ranges>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include "support.hpp"
#include "wrench/codec.hpp"
#include "wrench/error.hpp"
#include "wrench/value.hpp"

namespace {

// Functions rather than objects with static storage, because building a path
// allocates and an exception thrown before main cannot be caught.
std::filesystem::path schema_dir() { return {WRENCH_SCHEMA_DIR}; }

std::filesystem::path fixture_dir() {
    return std::filesystem::path(WRENCH_TESTDATA_DIR) / "canonical";
}

wrench::value parsed(std::string_view text) {
    const auto answer = wrench::json().decode(text);
    REQUIRE(answer.has_value());
    return *answer;
}

wrench::schema compiled(std::string_view text, std::string_view name = {}) {
    auto answer = wrench::schema::compile(parsed(text), name);
    REQUIRE(answer.has_value());
    return *answer;
}

// The shipped schema declaring an `$id`, which is how a fixture names the one it
// is an instance of (FR-3.6).
const wrench::schema& by_id(std::string_view id) {
    const std::span<const wrench::schemas::entry> shipped = wrench::schemas::all();
    const auto found = std::ranges::find_if(
        shipped, [id](const wrench::schemas::entry& one) { return one.id == id; });
    if (found == shipped.end()) {
        FAIL("no shipped schema declares ", id);
        return wrench::schemas::envelope();
    }
    return wrench::schemas::by_stem(found->stem);
}

// What the directory holds, read at run time, which is the authority every pack
// answers to.
std::vector<std::string> stems_on_disk() {
    std::vector<std::string> found;
    for (const auto& entry : std::filesystem::directory_iterator(schema_dir())) {
        const std::string leaf = entry.path().filename().string();
        if (leaf.ends_with(".schema.json")) {
            found.push_back(
                leaf.substr(0, leaf.size() - std::string(".schema.json").size()));
        }
    }
    std::ranges::sort(found);
    return found;
}

std::string trimmed(const std::string& text) {
    const std::size_t end = text.find_last_not_of(" \n\r\t");
    return end == std::string::npos ? text : text.substr(0, end + 1);
}

}  // namespace

// COVERS: FR-3.2 | property
TEST_CASE("what the pack carries is the bytes in the schema directory") {
    for (const wrench::schemas::entry& one : wrench::schemas::all()) {
        CAPTURE(one.stem);
        const std::filesystem::path file =
            schema_dir() / (std::string(one.stem) + ".schema.json");
        CHECK(std::string(one.text) == wrench::test::slurp(file));
    }
}

// COVERS: FR-3.7 | property
TEST_CASE("the shipped set is the directory and not a list in the source") {
    const std::span<const wrench::schemas::entry> set = wrench::schemas::all();
    std::vector<std::string> shipped(set.size());
    std::ranges::transform(set, shipped.begin(), [](const wrench::schemas::entry& one) {
        return std::string(one.stem);
    });
    std::ranges::sort(shipped);

    CHECK(shipped == stems_on_disk());
}

// The four accessors are names for members of that set. A schema added to the
// directory arrives through `by_stem` with nothing here edited, and this case is
// what says it still needs an accessor and a fixture of its own.
//
// COVERS: FR-5.7 | property
TEST_CASE("every shipped schema is reachable and each declares its own id") {
    CHECK(wrench::schemas::all().size() == 4);
    // Each accessor holds a schema that compiled, which is what separates a
    // shipped name from one the set does not hold: an empty document is either
    // an instance or a `validate` failure, and never a `schema` one.
    for (const wrench::schema* one : {&wrench::schemas::definitions(),
                                      &wrench::schemas::envelope(),
                                      &wrench::schemas::jig(),
                                      &wrench::schemas::manifest()}) {
        const auto answer = one->validate(wrench::value());
        const bool compiled =
            answer.has_value() || answer.error().step == wrench::step::validate;
        CHECK(compiled);
    }

    for (const wrench::schemas::entry& one : wrench::schemas::all()) {
        CAPTURE(one.stem);
        CHECK(one.id == parsed(one.text).at("$id").as_string());
        CHECK(one.id.ends_with(std::string(one.stem) + ".schema.json"));
    }
}

// COVERS: FR-3.7 | negative
TEST_CASE("a name the shipped set does not hold refuses every document") {
    const wrench::schema& absent = wrench::schemas::by_stem("nothing-like-this");
    const auto answer = absent.validate(parsed(R"({"success": true})"));

    REQUIRE_FALSE(answer.has_value());
    CHECK(answer.error().step == wrench::step::schema);
}

// COVERS: FR-3.5 | positive
TEST_CASE("a default schema is compiled against nothing and says so") {
    const wrench::schema nothing;
    const auto answer = nothing.validate(parsed(R"({"success": true})"));

    REQUIRE_FALSE(answer.has_value());
    CHECK(answer.error().step == wrench::step::schema);
    CHECK(answer.error().message == "no schema was compiled");
}

// Every shipped schema has a fixture that is an instance of it, and the fixture
// is validated against it rather than only compared byte for byte.
//
// COVERS: FR-3.8 | positive
TEST_CASE("every shipped schema validates the fixture that names it") {
    std::vector<std::string> checked;
    for (const auto& entry : std::filesystem::directory_iterator(fixture_dir())) {
        const std::filesystem::path named = entry.path() / "schema";
        if (!std::filesystem::exists(named)) {
            continue;
        }
        const std::string id = trimmed(wrench::test::slurp(named));
        CAPTURE(id);
        const auto document =
            wrench::yaml().decode(wrench::test::slurp(entry.path() / "input.yaml"));
        REQUIRE(document.has_value());
        CHECK(by_id(id).validate(*document).has_value());
        checked.push_back(id);
    }
    CHECK(checked.size() == wrench::schemas::all().size());
}

// COVERS: FR-3.1 | positive
TEST_CASE("the envelope is one schema and a jig is another, through the same call") {
    const wrench::value envelope =
        parsed(R"({"success": false, "reasons": [{"kind": "tool", "message": "no"}]})");

    CHECK(wrench::schemas::envelope().validate(envelope).has_value());
    CHECK_FALSE(wrench::schemas::jig().validate(envelope).has_value());
}

// COVERS: FR-3.3 | property
TEST_CASE("validation is indifferent to how the document was serialised") {
    const std::string as_yaml =
        "success: true\nreasons:\n  - kind: one\n    message: two\n";
    const std::string as_json =
        R"({"success": true, "reasons": [{"kind": "one", "message": "two"}]})";

    const auto from_yaml = wrench::yaml().decode(as_yaml);
    const auto from_json = wrench::json().decode(as_json);
    REQUIRE(from_yaml.has_value());
    REQUIRE(from_json.has_value());

    CHECK(*from_yaml == *from_json);
    CHECK(wrench::schemas::envelope().validate(*from_yaml).has_value());
    CHECK(wrench::schemas::envelope().validate(*from_json).has_value());
}

// COVERS: FR-3.4 | positive
TEST_CASE("a schema checks shape and not meaning") {
    const wrench::schema version =
        compiled(R"({"type": "object", "properties": {"v": {"type": "string"}}})");

    // A version number written unquoted parsed as a number, which is a defect in
    // the document that no schema can see: the value that arrived is a string
    // only when it was written as one.
    CHECK(version.validate(parsed(R"({"v": "1.20"})")).has_value());
    CHECK_FALSE(version.validate(parsed(R"({"v": 1.2})")).has_value());
}

// COVERS: FR-3.9 | positive
TEST_CASE("a document may declare its format version and may leave it out") {
    CHECK(wrench::schemas::envelope()
              .validate(parsed(R"({"version": "1.0.0", "success": true})"))
              .has_value());
    CHECK(wrench::schemas::envelope()
              .validate(parsed(R"({"success": true})"))
              .has_value());
}

// COVERS: FR-3.9 | negative
TEST_CASE("a version that is not semver is refused") {
    const auto answer = wrench::schemas::envelope().validate(
        parsed(R"({"version": "one", "success": true})"));

    REQUIRE_FALSE(answer.has_value());
    CHECK(answer.error().step == wrench::step::validate);
    CHECK(answer.error().message.starts_with("/version"));
}

// COVERS: FR-3.6 | positive
TEST_CASE("a shipped schema references another by the id it declares") {
    const wrench::value jig = parsed(
        R"({"version": "1.0.0", "definitions": {"line_length": 100},
            "tasks": [{"name": "format", "command": "gofmt -l ."}]})");

    CHECK(wrench::schemas::jig().validate(jig).has_value());
    // The reference is what refuses this: a definitions value has to be a
    // scalar, and only the referenced schema says so.
    CHECK_FALSE(wrench::schemas::jig()
                    .validate(parsed(R"({"definitions": {"a": {"b": 1}},
                                         "tasks": [{"name": "t", "command": "c"}]})"))
                    .has_value());
}

// COVERS: FR-3.10a | positive
TEST_CASE("a reference within the document resolves and constrains") {
    const wrench::schema own = compiled(
        R"({"type": "object", "properties": {"a": {"$ref": "#/$defs/small"}},
            "$defs": {"small": {"type": "integer", "maximum": 10}}})");

    CHECK(own.validate(parsed(R"({"a": 3})")).has_value());
    CHECK_FALSE(own.validate(parsed(R"({"a": 30})")).has_value());
}

// COVERS: FR-3.10 | negative
TEST_CASE("a reference outside the shipped set is refused rather than fetched") {
    const auto answer = wrench::schema::compile(
        parsed(R"({"$ref": "https://example.invalid/other.schema.json"})"));

    REQUIRE_FALSE(answer.has_value());
    CHECK(answer.error().step == wrench::step::schema);
}

// The refusal is one sentence, the same in every pack, naming the resolved
// reference so a reader is not sent looking for a string that resolved to
// something else.
//
// COVERS: FR-3.10d | negative
TEST_CASE("the refusal reads the same whatever refused it") {
    const auto answer = wrench::schema::compile(
        parsed(R"({"$ref": "https://example.invalid/other.schema.json"})"));

    REQUIRE_FALSE(answer.has_value());
    CHECK(answer.error().message ==
          "cannot resolve https://example.invalid/other.schema.json: a schema may "
          "reference the shipped schemas and its own fragments, and nothing else");
}

// COVERS: FR-3.10b | edge
TEST_CASE("a relative reference is judged once resolved and against the right base") {
    // Declaring no id, the compile name is the base, so the same text resolves
    // to a different reference than it would elsewhere.
    const auto named =
        wrench::schema::compile(parsed(R"({"$ref": "other.schema.json"})"),
                                "https://example.invalid/here.schema.json");
    REQUIRE_FALSE(named.has_value());
    CHECK(named.error().message.starts_with(
        "cannot resolve https://example.invalid/other.schema.json:"));

    // With an id, the id is the base and wins over the name.
    const auto declared = wrench::schema::compile(
        parsed(R"({"$id": "https://example.test/mine.schema.json",
                   "$ref": "other.schema.json"})"),
        "https://example.invalid/here.schema.json");
    REQUIRE_FALSE(declared.has_value());
    CHECK(declared.error().message.starts_with(
        "cannot resolve https://example.test/other.schema.json:"));
}

// COVERS: FR-3.10a | edge
TEST_CASE("a reference to a shipped id resolves through the same resolver") {
    const wrench::schema borrowed = compiled(
        R"({"$ref": "https://scriptedworld.github.io/wrench/envelope.schema.json"})");

    CHECK(borrowed.validate(parsed(R"({"success": true})")).has_value());
    CHECK_FALSE(borrowed.validate(parsed(R"({"success": "yes"})")).has_value());
}

// A keyword in an instance is data. Nothing here interprets `$ref`, `$id` or
// `$schema` in the document being validated, including a reference whose target
// exists.
//
// COVERS: FR-3.10c | edge
TEST_CASE("a keyword in the document being validated is an ordinary key") {
    const wrench::schema open = compiled(R"({"type": "object"})");
    const std::string pointing =
        R"({"$ref": "https://scriptedworld.github.io/wrench/jig.schema.json",
            "$id": "https://example.invalid/data",
            "$schema": "https://json-schema.org/draft/2020-12/schema"})";

    CHECK(open.validate(parsed(pointing)).has_value());
    // The same document against a schema that constrains it: the keys are read
    // as keys, so a type is what decides and not the reference.
    const wrench::schema strict =
        compiled(R"({"type": "object", "properties": {"$ref": {"type": "integer"}}})");
    CHECK_FALSE(strict.validate(parsed(pointing)).has_value());
}

// COVERS: FR-3.10 | edge
TEST_CASE("a caller may not redefine a shipped id") {
    const auto answer = wrench::schema::compile(
        parsed(R"({"$id": "https://scriptedworld.github.io/wrench/envelope.schema.json",
                   "type": "string"})"));

    REQUIRE_FALSE(answer.has_value());
    CHECK(answer.error().step == wrench::step::schema);
    CHECK(answer.error().message.starts_with("a schema may not redefine the shipped"));
}

// COVERS: FR-5.2 | positive
TEST_CASE("the validator is a 2020-12 implementation and not a subset of one") {
    const wrench::schema dialect = compiled(
        R"({"$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "propertyNames": {"pattern": "^[a-z]+$"},
            "if": {"required": ["a"]}, "then": {"required": ["b"]},
            "prefixItems": [{"type": "string"}]})");

    CHECK(dialect.validate(parsed(R"({"a": 1, "b": 2})")).has_value());
    CHECK_FALSE(dialect.validate(parsed(R"({"a": 1})")).has_value());
    CHECK_FALSE(dialect.validate(parsed(R"({"Upper": 1})")).has_value());
}

// COVERS: FR-5.2 | negative
TEST_CASE("a schema the validator cannot compile is a schema failure") {
    const auto answer =
        wrench::schema::compile(parsed(R"({"type": "object", "$ref": 4})"));

    REQUIRE_FALSE(answer.has_value());
    CHECK(answer.error().step == wrench::step::schema);
    CHECK_FALSE(answer.error().message.empty());
}

// A schema is a value, and a boolean is a schema in JSON Schema's own terms, so
// the compile call takes one rather than insisting on an object.
//
// COVERS: FR-3.5 | edge
TEST_CASE("a boolean is a schema and compiles") {
    const wrench::schema anything = compiled("true");
    const wrench::schema nothing = compiled("false");

    CHECK(anything.validate(parsed(R"({"a": 1})")).has_value());
    CHECK_FALSE(nothing.validate(parsed(R"({"a": 1})")).has_value());
}
