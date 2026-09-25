// JSON, both directions, over jsoncons.
//
// Canonical form is two-space indent, one key to a line, keys sorted and a
// trailing newline (FR-4.6), which is what `deno fmt` writes for everything but
// the sorting. The layout comes from the library's own options; what the pack
// supplies is the float spelling and the widening, the two places where the
// library's answer and the contract's differ.
//
// Three differences the pack settles, none of them a reason to refuse the
// library:
//
//   A float is spelled by `canonical_float` and handed back to the library as a
//   decimal string tagged bigdec, which it writes unquoted. That is how FR-4.8
//   reaches the output without a hand-written emitter, and it is also why
//   jsoncons writing `-0.0` as `0.0` never shows.
//
//   Past the signed 64-bit range a value widens to a float and the widening is
//   visible (FR-4.10). Above int64's maximum the library keeps an exact uint64,
//   so the widening happens here; further out it has already widened.
//
//   `-0` is a negative zero float in JSON (FR-4.11) and jsoncons cannot say so:
//   its parser converts an integer token to a number before anything can see
//   the text, so `-0` and `0` arrive identical. The one token that needs its
//   sign is respelled before the parse.

// Two of the includes below are inside jsoncons rather than at its surface.
// Reading a number instantiates them, so include-what-you-use names them, and
// the jig passes no mapping file that could say otherwise.
#include <cstddef>
#include <cstdint>
#include <expected>
#include <jsoncons/basic_json.hpp>
#include <jsoncons/json_exception.hpp>
#include <jsoncons/json_options.hpp>
#include <jsoncons/key_value.hpp>
#include <jsoncons/semantic_tag.hpp>
#include <jsoncons/utility/read_number.hpp>
#include <limits>
#include <optional>
#include <string>
#include <string_view>
#include <system_error>
#include <utility>
#include <vector>

#include "wrench/canonical.hpp"
#include "wrench/codec.hpp"
#include "wrench/error.hpp"
#include "wrench/value.hpp"

namespace wrench {

namespace {

// ---- reading -----------------------------------------------------------------

// Whether the `-0` at `at` is an integer token and not the start of `-0.5` or
// `-0e1`, both of which the library already reads as a signed zero.
bool is_bare_negative_zero(std::string_view bytes, std::size_t at) {
    if (bytes[at] != '-' || at + 1 >= bytes.size() || bytes[at + 1] != '0') {
        return false;
    }
    const std::size_t after = at + 2;
    if (after >= bytes.size()) {
        return true;
    }
    const char next = bytes[after];
    return next != '.' && next != 'e' && next != 'E' && (next < '0' || next > '9');
}

// The bytes with every `-0` integer token written `-0.0`, or nothing where the
// document holds none. A `-` outside a string starts a number in JSON, so
// tracking the strings is the whole of what this has to get right.
std::optional<std::string> respell_negative_zero(std::string_view bytes) {
    std::optional<std::string> respelled;
    bool inside = false;
    bool escaped = false;
    for (std::size_t at = 0; at < bytes.size(); ++at) {
        const char one = bytes[at];
        if (inside) {
            inside = one != '"' || escaped;
            escaped = one == '\\' && !escaped;
        } else if (one == '"') {
            inside = true;
        } else if (is_bare_negative_zero(bytes, at)) {
            if (!respelled.has_value()) {
                respelled = std::string(bytes.substr(0, at));
            }
            respelled->append("-0.0");
            ++at;
            continue;
        }
        if (respelled.has_value()) {
            respelled->push_back(one);
        }
    }
    return respelled;
}

// An integer above the signed 64-bit maximum, widened where the library kept it
// exact. Further out than uint64 it arrives as a float already, the parse being
// told not to keep a big number whole.
void widen(value& document) {
    if (document.is_object()) {
        for (auto& member : document.object_range()) {
            widen(member.value());
        }
    } else if (document.is_array()) {
        for (value& element : document.array_range()) {
            widen(element);
        }
    } else if (document.is_uint64() &&
               document.as<std::uint64_t>() >
                   static_cast<std::uint64_t>(
                       std::numeric_limits<std::int64_t>::max())) {
        document = value(document.as_double());
    }
}

// ---- writing -----------------------------------------------------------------

// What the library is told about layout. Nothing here decides a value's
// spelling; every number has already been spelled by the time this is used.
jsoncons::json_options layout() {
    jsoncons::json_options options;
    options.indent_size(2);
    options.spaces_around_colon(jsoncons::spaces_option::space_after);
    options.spaces_around_comma(jsoncons::spaces_option::no_spaces);
    // One key to a line, and nothing collapsed onto one because it happened to
    // be short, which is the difference between a canonical form and a
    // formatter.
    options.object_object_line_splits(jsoncons::line_split_kind::multi_line);
    options.object_array_line_splits(jsoncons::line_split_kind::multi_line);
    options.array_array_line_splits(jsoncons::line_split_kind::multi_line);
    options.array_object_line_splits(jsoncons::line_split_kind::multi_line);
    options.line_length_limit(0);
    return options;
}

failure outside_the_model(const value& document) {
    return failure{.step = step::encode,
                   .message = "a value outside the model has no canonical form: " +
                              document.to_string(),
                   .cause = {}};
}

// A string is a string, and not one of the library's other kinds wearing a
// string's storage. A tagged string is a big number, a byte string, a date or a
// regular expression to the library, and a big number is written unquoted, so
// the output would say something the value did not.
//
// Two tags are a plain string: none, and the noesc the parser sets on a string
// that needed no unescaping. Both mean the same thing to a reader.
bool plainly_a_string(const value& document) {
    return document.tag() == jsoncons::semantic_tag::none ||
           document.tag() == jsoncons::semantic_tag::noesc;
}

result<value> respelled(const value& document);

result<value> respelled_object(const value& document) {
    value rebuilt = value();
    for (const auto& member : document.object_range()) {
        result<value> held = respelled(member.value());
        if (!held.has_value()) {
            return std::unexpected(held.error());
        }
        rebuilt[member.key()] = std::move(*held);
    }
    return rebuilt;
}

result<value> respelled_array(const value& document) {
    value rebuilt = value::make_array();
    for (const value& element : document.array_range()) {
        result<value> held = respelled(element);
        if (!held.has_value()) {
            return std::unexpected(held.error());
        }
        rebuilt.push_back(std::move(*held));
    }
    return rebuilt;
}

// The same tree with every float spelled the one way FR-4.8 allows, and a
// refusal where a value has no canonical form at all.
result<value> respelled(const value& document) {
    if (document.is_object()) {
        return respelled_object(document);
    }
    if (document.is_array()) {
        return respelled_array(document);
    }
    if (document.is_double()) {
        const result<std::string> number = canonical_float(document.as_double());
        if (!number.has_value()) {
            return std::unexpected(number.error());
        }
        // Tagged as a decimal, which is what makes the library write the digits
        // bare rather than as a quoted string.
        return value(*number, jsoncons::semantic_tag::bigdec);
    }
    if (document.is_string() && !plainly_a_string(document)) {
        return std::unexpected(outside_the_model(document));
    }
    if (document.is_null() || document.is_bool() || document.is_int64() ||
        document.is_uint64() || document.is_string()) {
        return document;
    }
    return std::unexpected(outside_the_model(document));
}

}  // namespace

result<value> json_codec::decode(std::string_view bytes) const {
    const std::optional<std::string> respelled = respell_negative_zero(bytes);
    const std::string_view source =
        respelled.has_value() ? std::string_view(*respelled) : bytes;
    jsoncons::json_options options;
    // A number too big for a 64-bit integer becomes a float here rather than a
    // big number the pack would have to widen itself.
    options.lossless_bignum(false);
    try {
        value document = value::parse(source, options);
        widen(document);
        return document;
    } catch (const jsoncons::json_exception& thrown) {
        return std::unexpected(
            failure{.step = step::parse, .message = thrown.what(), .cause = {}});
    }
}

result<std::string> json_codec::encode(const value& document) const {
    const result<value> spelled = respelled(document);
    if (!spelled.has_value()) {
        return std::unexpected(spelled.error());
    }
    std::string out;
    spelled->dump(out, layout(), jsoncons::indenting::indent);
    // A trailing newline, so the file is a line-oriented tool's idea of a file.
    out.push_back('\n');
    return out;
}

const codec& json() {
    static const json_codec one;
    return one;
}

}  // namespace wrench
