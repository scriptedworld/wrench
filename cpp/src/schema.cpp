// Two of the includes below are inside jsoncons rather than at its surface.
// Compiling the schema factory instantiates both, so include-what-you-use names
// them, and the jig passes no mapping file that could say otherwise.
#include "wrench/schema.hpp"

#include <algorithm>
#include <array>
#include <exception>
#include <expected>
#include <functional>
#include <jsoncons/basic_json.hpp>
#include <jsoncons/detail/make_obj_using_allocator.hpp>
#include <jsoncons/utility/read_number.hpp>
#include <jsoncons/utility/uri.hpp>
#include <jsoncons_ext/jsonschema/common/validator.hpp>
#include <jsoncons_ext/jsonschema/json_schema.hpp>
#include <jsoncons_ext/jsonschema/json_schema_factory.hpp>
#include <jsoncons_ext/jsonschema/jsonschema_error.hpp>
#include <jsoncons_ext/jsonschema/validation_message.hpp>
#include <map>
#include <memory>
#include <optional>
#include <ranges>
#include <span>
#include <string>
#include <string_view>
#include <system_error>
#include <utility>
#include <vector>
#include <wrench/shipped.hpp>

#include "wrench/codec.hpp"
#include "wrench/error.hpp"
#include "wrench/value.hpp"

namespace wrench {

// What a compiled schema holds. Separated out so `schema` stays a value a
// caller can copy, and so the validator is built once however many documents
// are checked against it.
struct schema::state {
    jsoncons::jsonschema::json_schema<value> validator;
};

namespace {

// The refusal FR-3.10d fixes, word for word in every pack, so a consumer
// reading it cannot tell which language produced it. It names the resolved
// reference and not the text as written (FR-3.10b).
std::string cannot_resolve(const std::string& reference) {
    return "cannot resolve " + reference +
           ": a schema may reference the shipped schemas and its own fragments, "
           "and nothing else";
}

// One shipped schema after decoding: the name of its file, its bytes, the `$id`
// it declares, and the document itself.
struct holding {
    std::string_view stem;
    std::string_view text;
    std::string id;
    value document;
};

// The shipped set, decoded through the pack's own JSON codec so a malformed
// shipped file is a failure of this pack's family and not a thrown library
// exception. A document that will not decode, or that declares no `$id`, is
// left out: it is then absent from `all()` and from every accessor, and the
// suite fails rather than the pack pretending to ship it.
std::vector<holding> decode_shipped() {
    std::vector<holding> built;
    for (const shipped::document& one : shipped::documents) {
        const result<value> document = json().decode(one.text);
        if (!document.has_value() || !document->contains("$id")) {
            continue;
        }
        built.push_back(holding{.stem = one.stem,
                                .text = one.text,
                                .id = document->at("$id").as_string(),
                                .document = *document});
    }
    return built;
}

const std::vector<holding>& shipped_set() {
    static const std::vector<holding> set = decode_shipped();
    return set;
}

// The resolver the pack installs on every compile: the shipped set by the `$id`
// each declares, and a refusal for everything else (FR-3.10). Not the network,
// not the disk, and with no way to ask for more.
//
// The 2020-12 meta-schema never reaches here. jsoncons answers that from its own
// copy, which is what lets a schema compile with no network at all.
value resolve(const jsoncons::uri& reference) {
    const std::string& asked = reference.string();
    // A copy, because the base is a URI built here and its text would not
    // outlive the expression.
    const std::string base = reference.base().string();
    const auto found =
        std::ranges::find_if(shipped_set(), [&asked, &base](const holding& held) {
            return held.id == asked || held.id == base;
        });
    if (found == shipped_set().end()) {
        throw jsoncons::jsonschema::schema_error(cannot_resolve(asked));
    }
    return found->document;
}

// Whether the document claims an `$id` a shipped schema already declares while
// being some other document. A shipped schema fixes what an envelope means, and
// a caller's copy does not get to decide it, so the compile is refused rather
// than quietly preferring one of the two.
std::optional<failure> redefines_shipped(const value& document) {
    if (!document.is_object() || !document.contains("$id")) {
        return std::nullopt;
    }
    const std::string declared = document.at("$id").as_string();
    const bool taken =
        std::ranges::any_of(shipped_set(), [&declared, &document](const holding& held) {
            return held.id == declared && held.document != document;
        });
    if (taken) {
        return failure{.step = step::schema,
                       .message = "a schema may not redefine the shipped " + declared,
                       .cause = {}};
    }
    return std::nullopt;
}

// Where inside the document the validator objected, and to what. A failure at
// the root has no location, so the location is written only where there is one.
std::string reported_as(const jsoncons::jsonschema::validation_message& message) {
    const std::string where = message.instance_location().string();
    if (where.empty()) {
        return message.message();
    }
    return where + ": " + message.message();
}

}  // namespace

schema::schema()
    : schema(nullptr,
             failure{.step = step::schema,
                     .message = "no schema was compiled",
                     .cause = {}}) {}

schema::schema(std::shared_ptr<const state> held, failure refusal)
    : held_(std::move(held)), refusal_(std::move(refusal)) {}

result<schema> schema::compile(const value& document, std::string_view name) {
    if (const std::optional<failure> clash = redefines_shipped(document)) {
        return std::unexpected(*clash);
    }
    try {
        // The library refuses an empty retrieval reference outright, so a
        // document compiled under no name at all goes through the overload that
        // asks for none. It is the same compile either way.
        auto held = std::make_shared<const state>(state{
            .validator = name.empty()
                             ? jsoncons::jsonschema::make_json_schema(document, resolve)
                             : jsoncons::jsonschema::make_json_schema(
                                   document, std::string(name), resolve)});
        return schema(std::move(held), failure{});
    } catch (const std::exception& thrown) {
        // Whatever stopped the schema from compiling, including the resolver's
        // own refusal, which is already the sentence FR-3.10d fixes.
        return std::unexpected(
            failure{.step = step::schema, .message = thrown.what(), .cause = {}});
    }
}

result<void> schema::validate(const value& instance) const {
    if (held_ == nullptr) {
        return std::unexpected(refusal_);
    }
    std::string objection;
    held_->validator.validate(
        instance,
        [&objection](const jsoncons::jsonschema::validation_message& message) {
            objection = reported_as(message);
            // The first objection is the one reported. A caller is told what to
            // fix, and a document with one fault and a document with twenty are
            // both refused.
            return jsoncons::jsonschema::walk_result::abort;
        });
    if (!objection.empty()) {
        return std::unexpected(
            failure{.step = step::validate, .message = objection, .cause = {}});
    }
    return {};
}

namespace schemas {

namespace {

// Every shipped schema compiled once, by the name of its file. One that will not
// compile is left out, so it reaches a caller as the same refusal an unknown
// name does and the suite is what reports which.
std::map<std::string, schema, std::less<>> compile_shipped() {
    std::map<std::string, schema, std::less<>> built;
    for (const entry& one : all()) {
        const result<value> document = json().decode(one.text);
        if (!document.has_value()) {
            continue;
        }
        result<schema> compiled = schema::compile(*document, one.id);
        if (compiled.has_value()) {
            built.emplace(std::string(one.stem), std::move(*compiled));
        }
    }
    return built;
}

}  // namespace

std::span<const entry> all() {
    static const std::vector<entry> set = [] {
        std::vector<entry> built(shipped_set().size());
        std::ranges::transform(shipped_set(), built.begin(), [](const holding& held) {
            return entry{.stem = held.stem, .id = held.id, .text = held.text};
        });
        return built;
    }();
    return set;
}

const schema& by_stem(std::string_view stem) {
    static const std::map<std::string, schema, std::less<>> compiled =
        compile_shipped();
    const auto found = compiled.find(stem);
    if (found == compiled.end()) {
        // Total by construction: a name the set does not hold refuses every
        // document rather than leaving a caller with nothing to return.
        static const schema absent;
        return absent;
    }
    return found->second;
}

const schema& definitions() { return by_stem("definitions"); }

const schema& envelope() { return by_stem("envelope"); }

const schema& jig() { return by_stem("jig"); }

const schema& manifest() { return by_stem("manifest"); }

}  // namespace schemas

}  // namespace wrench
