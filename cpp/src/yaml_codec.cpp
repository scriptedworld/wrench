// YAML, both directions, over libyaml's event interface.
//
// The emitter applies the four adapters and nothing else decides the layout:
// keys arrive sorted because `wrench::value` keeps them that way, every string
// and key is double quoted, a float is spelled by `canonical_float`, and null is
// written as the word. Two settings sit beside them, both settings and not code:
// the line width off, so a long scalar is never wrapped, and unicode passed
// through rather than escaped.
//
// The decoder does the half libyaml leaves to its caller. libyaml hands back a
// scalar's text and the flags saying how it was written, so turning `no`, `10`
// and `2026-01-01` into values is this file's work. The rule is one line:
// resolve a scalar only where it was written plain, so a quoted scalar and a
// tagged one are strings and a plain one is looked up in the table below.
//
//     no yes on off      strings         null ~ and empty    null
//     true false         booleans        10 010              integer 10
//     0x10               integer 16      1_000               integer 1000
//     1.20               float 1.2       1e3                 float 1000.0
//     2026-01-01         string          12:30               string
//     .inf .nan          floats, which canonical form then refuses on the way out
//
// Two shapes this does not reach, named so a reader stops looking. A merge key
// is an ordinary key spelled `<<`, so a document using one gets a mapping under
// that name rather than the merge YAML 1.1 describes. An explicit tag is not
// honoured beyond leaving the scalar as the string it was written as.

#include <yaml.h>

// Three of the includes below are inside jsoncons rather than at its surface.
// Building and reading a value instantiates them, so include-what-you-use names
// them, and the jig passes no mapping file that could say otherwise.
#include <algorithm>
#include <cctype>
#include <charconv>
#include <cstdint>
#include <cstring>
#include <expected>
#include <functional>
#include <jsoncons/basic_json.hpp>
#include <jsoncons/detail/make_obj_using_allocator.hpp>
#include <jsoncons/key_value.hpp>
#include <jsoncons/semantic_tag.hpp>
#include <jsoncons/utility/conversion.hpp>
#include <jsoncons/utility/read_number.hpp>
#include <limits>
#include <map>
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

// ---- resolving a plain scalar ------------------------------------------------

// Which base a number's prefix declares.
constexpr int decimal = 10;
constexpr int octal = 8;
constexpr int hexadecimal = 16;

// The text with every underscore dropped, which is what a digit group separator
// amounts to once the value is read.
std::string without_separators(std::string_view text) {
    std::string kept(text);
    std::erase(kept, '_');
    return kept;
}

// One of the spellings the table gives for nothing at all.
bool is_null_word(std::string_view text) {
    return text.empty() || text == "null" || text == "Null" || text == "NULL" ||
           text == "~";
}

std::optional<bool> as_boolean(std::string_view text) {
    if (text == "true" || text == "True" || text == "TRUE") {
        return true;
    }
    if (text == "false" || text == "False" || text == "FALSE") {
        return false;
    }
    return std::nullopt;
}

// A number as it was written: the sign, the base its prefix declares, and the
// digits with the prefix and the separators gone.
struct digits {
    bool negative = false;
    int base = decimal;
    std::string body;
};

digits taken_apart(std::string_view text) {
    digits taken;
    std::string rest = without_separators(text);
    if (rest.starts_with('-') || rest.starts_with('+')) {
        taken.negative = rest.starts_with('-');
        rest.erase(0, 1);
    }
    if (rest.starts_with("0x") || rest.starts_with("0X")) {
        taken.base = hexadecimal;
        rest.erase(0, 2);
    } else if (rest.starts_with("0o") || rest.starts_with("0O")) {
        taken.base = octal;
        rest.erase(0, 2);
    }
    taken.body = std::move(rest);
    return taken;
}

// Every character is a digit the declared base has, and there is at least one.
bool all_digits(const digits& taken) {
    const int base = taken.base;
    return !taken.body.empty() &&
           std::ranges::all_of(taken.body, [base](const char one) {
               if (base == hexadecimal) {
                   return std::isxdigit(static_cast<unsigned char>(one)) != 0;
               }
               return one >= '0' && one <= (base == octal ? '7' : '9');
           });
}

// Past the signed 64-bit range the value widens to a float, and FR-4.8 then
// makes the widening visible in the spelling (FR-4.10). Base ten is handed to
// the standard library, which rounds the whole digit string correctly; the other
// two bases are accumulated, there being no such conversion for them.
double widened(const digits& taken) {
    double magnitude = 0;
    if (taken.base == decimal) {
        std::from_chars(
            taken.body.data(), taken.body.data() + taken.body.size(), magnitude);
    } else {
        for (const char one : taken.body) {
            const int digit =
                one <= '9' ? one - '0' : (std::tolower(one) - 'a') + decimal;
            magnitude = (magnitude * taken.base) + digit;
        }
    }
    return taken.negative ? -magnitude : magnitude;
}

std::optional<value> as_integer(std::string_view text) {
    const digits taken = taken_apart(text);
    if (!all_digits(taken)) {
        return std::nullopt;
    }
    std::uint64_t magnitude = 0;
    const std::from_chars_result read =
        std::from_chars(taken.body.data(),
                        taken.body.data() + taken.body.size(),
                        magnitude,
                        taken.base);
    const auto limit =
        static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max());
    if (read.ec == std::errc{} && magnitude <= limit + (taken.negative ? 1U : 0U)) {
        const auto signed_magnitude = static_cast<std::int64_t>(magnitude);
        return value(taken.negative ? -signed_magnitude : signed_magnitude);
    }
    return value(widened(taken));
}

// How many digits stand at `at`, which is what the float shape is counted in.
std::size_t digit_run(std::string_view text, std::size_t at) {
    std::size_t seen = 0;
    while (at + seen < text.size() && text[at + seen] >= '0' &&
           text[at + seen] <= '9') {
        ++seen;
    }
    return seen;
}

// Whether the text is a decimal float and nothing else. The standard library's
// conversion accepts `inf` and `nan` as words, which YAML spells `.inf` and
// `.nan`, so the shape is checked here rather than left to it.
bool looks_like_float(std::string_view text) {
    std::size_t at = 0;
    if (text.starts_with('-') || text.starts_with('+')) {
        at = 1;
    }
    const std::size_t before = digit_run(text, at);
    at += before;
    std::size_t after = 0;
    bool dotted = false;
    if (at < text.size() && text[at] == '.') {
        dotted = true;
        after = digit_run(text, at + 1);
        at += 1 + after;
    }
    bool powered = false;
    if (at < text.size() && (text[at] == 'e' || text[at] == 'E')) {
        std::size_t power = at + 1;
        if (power < text.size() && (text[power] == '-' || text[power] == '+')) {
            ++power;
        }
        const std::size_t run = digit_run(text, power);
        powered = run > 0;
        at = power + run;
    }
    return at == text.size() && before + after > 0 && (dotted || powered);
}

std::optional<value> as_float(std::string_view text) {
    const std::string cleaned = without_separators(text);
    std::string_view body = cleaned;
    const bool negative = body.starts_with('-');
    if (negative || body.starts_with('+')) {
        body.remove_prefix(1);
    }
    if (body == ".inf" || body == ".Inf" || body == ".INF") {
        const double infinity = std::numeric_limits<double>::infinity();
        return value(negative ? -infinity : infinity);
    }
    if (body == ".nan" || body == ".NaN" || body == ".NAN") {
        return value(std::numeric_limits<double>::quiet_NaN());
    }
    if (!looks_like_float(cleaned)) {
        return std::nullopt;
    }
    // The sign is applied here rather than left to the conversion, which takes a
    // leading minus and refuses a leading plus. Handing it the whole text read
    // `+1.5` as nothing at all.
    double number = 0;
    std::from_chars(body.data(), body.data() + body.size(), number);
    return value(negative ? -number : number);
}

// The table in the header comment, applied to a scalar written plain. Anything
// that is none of these is the string it was written as, which is what keeps a
// timestamp and a version number whole.
value resolved(std::string_view text) {
    if (is_null_word(text)) {
        return value::null();
    }
    if (const std::optional<bool> answer = as_boolean(text)) {
        return {*answer};
    }
    if (const std::optional<value> number = as_integer(text)) {
        return *number;
    }
    if (const std::optional<value> number = as_float(text)) {
        return *number;
    }
    return {text};
}

// ---- reading -----------------------------------------------------------------

std::string_view text_of(const yaml_char_t* bytes, std::size_t length) {
    return {reinterpret_cast<const char*>(bytes), length};
}

std::string_view name_of(const yaml_char_t* anchor) {
    if (anchor == nullptr) {
        return {};
    }
    return {reinterpret_cast<const char*>(anchor),
            std::strlen(reinterpret_cast<const char*>(anchor))};
}

// The parser, the event it is sitting on, and the whole of libyaml's lifetime
// rules in one place: every event is deleted before the next is read, and the
// parser is deleted whichever way the read goes.
class stream {
   public:
    explicit stream(std::string_view bytes) {
        yaml_parser_initialize(&parser_);
        yaml_parser_set_input_string(
            &parser_,
            reinterpret_cast<const unsigned char*>(bytes.data()),
            bytes.size());
    }

    ~stream() {
        yaml_event_delete(&event_);
        yaml_parser_delete(&parser_);
    }

    stream(const stream&) = delete;
    stream& operator=(const stream&) = delete;
    stream(stream&&) = delete;
    stream& operator=(stream&&) = delete;

    // The next event, or false where the document could not be read.
    bool next() {
        yaml_event_delete(&event_);
        event_ = {};
        return yaml_parser_parse(&parser_, &event_) != 0;
    }

    [[nodiscard]] const yaml_event_t& at() const { return event_; }

    // What libyaml said, with where it said it, which is the half of a parse
    // failure a person acts on.
    [[nodiscard]] failure problem() const {
        std::string message = parser_.problem != nullptr
                                  ? parser_.problem
                                  : "the document could not be read";
        message += " at line ";
        message += std::to_string(parser_.problem_mark.line + 1);
        message += " column ";
        message += std::to_string(parser_.problem_mark.column + 1);
        return {.step = step::parse, .message = std::move(message), .cause = {}};
    }

   private:
    yaml_parser_t parser_{};
    yaml_event_t event_{};
};

failure refused(std::string what) {
    return {.step = step::parse, .message = std::move(what), .cause = {}};
}

// Anchors seen so far, by the name each was declared under, so an alias is the
// value its anchor held.
using anchors = std::map<std::string, value, std::less<>>;

result<value> read_node(stream& in, anchors& seen);

result<value> read_sequence(stream& in, anchors& seen) {
    value list = value::make_array();
    while (true) {
        if (!in.next()) {
            return std::unexpected(in.problem());
        }
        if (in.at().type == YAML_SEQUENCE_END_EVENT) {
            return list;
        }
        result<value> element = read_node(in, seen);
        if (!element.has_value()) {
            return std::unexpected(element.error());
        }
        list.push_back(std::move(*element));
    }
}

// A key is a string or the document is refused (FR-2.9). Stringifying one is
// not reversible, so the pack does not do it.
result<std::string> read_key(stream& in, anchors& seen) {
    result<value> key = read_node(in, seen);
    if (!key.has_value()) {
        return std::unexpected(key.error());
    }
    if (!key->is_string()) {
        return std::unexpected(refused(
            "a mapping key that is not a string is refused: " + key->to_string()));
    }
    return key->as_string();
}

result<value> read_mapping(stream& in, anchors& seen) {
    value mapping = value();
    while (true) {
        if (!in.next()) {
            return std::unexpected(in.problem());
        }
        if (in.at().type == YAML_MAPPING_END_EVENT) {
            return mapping;
        }
        result<std::string> key = read_key(in, seen);
        if (!key.has_value()) {
            return std::unexpected(key.error());
        }
        if (!in.next()) {
            return std::unexpected(in.problem());
        }
        result<value> held = read_node(in, seen);
        if (!held.has_value()) {
            return std::unexpected(held.error());
        }
        mapping[*key] = std::move(*held);
    }
}

// The alias's value, or a refusal where nothing declared that anchor. libyaml
// reports an undefined alias itself, so this answers the case where a document
// aliases an anchor declared later.
result<value> read_alias(const stream& in, const anchors& seen) {
    const std::string_view anchor = name_of(in.at().data.alias.anchor);
    const auto found = seen.find(anchor);
    if (found == seen.end()) {
        return std::unexpected(
            refused("an alias names an anchor that is not declared yet: " +
                    std::string(anchor)));
    }
    return found->second;
}

// The node the stream is sitting on, whole, with the stream left on its last
// event. An anchor is recorded once the node it names is complete, which is what
// makes an alias to a mapping the mapping and not a fragment of it.
result<value> read_node(stream& in, anchors& seen) {
    const yaml_event_t& event = in.at();
    if (event.type == YAML_ALIAS_EVENT) {
        return read_alias(in, seen);
    }
    std::string anchor;
    result<value> held;
    if (event.type == YAML_SCALAR_EVENT) {
        anchor = name_of(event.data.scalar.anchor);
        const std::string_view text =
            text_of(event.data.scalar.value, event.data.scalar.length);
        held = event.data.scalar.plain_implicit != 0 ? resolved(text) : value(text);
    } else if (event.type == YAML_SEQUENCE_START_EVENT) {
        anchor = name_of(event.data.sequence_start.anchor);
        held = read_sequence(in, seen);
    } else if (event.type == YAML_MAPPING_START_EVENT) {
        anchor = name_of(event.data.mapping_start.anchor);
        held = read_mapping(in, seen);
    } else {
        return std::unexpected(
            refused("a document holds something that is not a value"));
    }
    if (held.has_value() && !anchor.empty()) {
        seen.insert_or_assign(anchor, *held);
    }
    return held;
}

// Past the document: what follows the one value a file holds.
//
// A stream may carry several documents and this codec reads one, because a call
// answering with a value has nowhere to put the second. The refusal says so
// rather than returning the first and dropping the rest.
result<void> read_to_end(stream& in) {
    if (!in.next()) {
        return std::unexpected(in.problem());
    }
    if (in.at().type != YAML_DOCUMENT_END_EVENT) {
        return std::unexpected(refused("a document holds more than one value"));
    }
    if (!in.next()) {
        return std::unexpected(in.problem());
    }
    if (in.at().type != YAML_STREAM_END_EVENT) {
        return std::unexpected(refused("a file holds more than one document"));
    }
    return {};
}

// ---- writing -----------------------------------------------------------------

int keep(void* data, unsigned char* buffer, std::size_t size) {
    auto* out = static_cast<std::string*>(data);
    out->append(reinterpret_cast<const char*>(buffer), size);
    return 1;
}

// The emitter, its settings, and the bytes it has produced so far.
class sink {
   public:
    explicit sink(std::string* out) {
        yaml_emitter_initialize(&emitter_);
        yaml_emitter_set_output(&emitter_, keep, out);
        // Unicode through rather than escaped, and no line width at all, so a
        // long scalar is one line however long it is.
        yaml_emitter_set_unicode(&emitter_, 1);
        yaml_emitter_set_width(&emitter_, -1);
    }

    ~sink() { yaml_emitter_delete(&emitter_); }

    sink(const sink&) = delete;
    sink& operator=(const sink&) = delete;
    sink(sink&&) = delete;
    sink& operator=(sink&&) = delete;

    // One event out. The event is initialised by the caller and is spent here
    // whether or not the emitter took it.
    bool emit(yaml_event_t& event) { return yaml_emitter_emit(&emitter_, &event) != 0; }

    [[nodiscard]] failure problem() const {
        std::string message = emitter_.problem != nullptr
                                  ? emitter_.problem
                                  : "the value could not be written";
        return failure{
            .step = step::encode, .message = std::move(message), .cause = {}};
    }

   private:
    yaml_emitter_t emitter_{};
};

// A scalar, quoted or bare. Quoted is every string and every key, which is the
// adapter that makes escaping possible at all: a single-quoted scalar has no
// escapes, so a control character in one would be written raw. Bare is every
// other kind, which is what keeps a boolean a boolean.
bool write_scalar(sink& out, std::string_view text, bool quoted) {
    yaml_event_t event;
    // A scalar carrying neither a tag nor an implicit flag is refused by
    // libyaml, and the flag that has to say the tag is implied is the one
    // matching the style.
    yaml_scalar_event_initialize(
        &event,
        nullptr,
        nullptr,
        reinterpret_cast<yaml_char_t*>(const_cast<char*>(text.data())),
        static_cast<int>(text.size()),
        quoted ? 0 : 1,
        quoted ? 1 : 0,
        quoted ? YAML_DOUBLE_QUOTED_SCALAR_STYLE : YAML_PLAIN_SCALAR_STYLE);
    return out.emit(event);
}

result<void> write_node(sink& out, const value& document);

result<void> write_sequence(sink& out, const value& document) {
    yaml_event_t event;
    yaml_sequence_start_event_initialize(
        &event, nullptr, nullptr, 1, YAML_BLOCK_SEQUENCE_STYLE);
    if (!out.emit(event)) {
        return std::unexpected(out.problem());
    }
    for (const value& element : document.array_range()) {
        const result<void> written = write_node(out, element);
        if (!written.has_value()) {
            return written;
        }
    }
    yaml_sequence_end_event_initialize(&event);
    if (!out.emit(event)) {
        return std::unexpected(out.problem());
    }
    return {};
}

result<void> write_mapping(sink& out, const value& document) {
    yaml_event_t event;
    yaml_mapping_start_event_initialize(
        &event, nullptr, nullptr, 1, YAML_BLOCK_MAPPING_STYLE);
    if (!out.emit(event)) {
        return std::unexpected(out.problem());
    }
    // The members arrive sorted by key, that being a property of the value type
    // rather than something this loop does, which is the first adapter.
    for (const auto& member : document.object_range()) {
        if (!write_scalar(out, member.key(), true)) {
            return std::unexpected(out.problem());
        }
        const result<void> written = write_node(out, member.value());
        if (!written.has_value()) {
            return written;
        }
    }
    yaml_mapping_end_event_initialize(&event);
    if (!out.emit(event)) {
        return std::unexpected(out.problem());
    }
    return {};
}

// A string is a string, and not one of the library's other kinds wearing a
// string's storage: a tagged string is a big number, a byte string or a date to
// the library, none of which is in the model FR-2.9 fixes. The noesc tag its
// parser sets on a string needing no unescaping means a plain string, as none
// does.
bool plainly_a_string(const value& document) {
    return document.tag() == jsoncons::semantic_tag::none ||
           document.tag() == jsoncons::semantic_tag::noesc;
}

// A scalar in the model, spelled the one way canonical form allows. A value with
// no canonical form is refused rather than guessed at (FR-4.1), which is what
// NaN and the infinities reach.
result<void> write_leaf(sink& out, const value& document) {
    std::string spelled;
    bool quoted = false;
    if (document.is_null()) {
        spelled = "null";
    } else if (document.is_bool()) {
        spelled = document.as_bool() ? "true" : "false";
    } else if (document.is_double()) {
        const result<std::string> number = canonical_float(document.as_double());
        if (!number.has_value()) {
            return std::unexpected(number.error());
        }
        spelled = *number;
    } else if (document.is_int64() || document.is_uint64()) {
        spelled = document.to_string();
    } else if (document.is_string() && plainly_a_string(document)) {
        spelled = document.as_string();
        quoted = true;
    } else {
        return std::unexpected(
            failure{.step = step::encode,
                    .message = "a value outside the model has no canonical form: " +
                               document.to_string(),
                    .cause = {}});
    }
    if (!write_scalar(out, spelled, quoted)) {
        return std::unexpected(out.problem());
    }
    return {};
}

result<void> write_node(sink& out, const value& document) {
    if (document.is_object()) {
        return write_mapping(out, document);
    }
    if (document.is_array()) {
        return write_sequence(out, document);
    }
    return write_leaf(out, document);
}

// The document, from stream start to stream end. Implicit at both ends, so
// nothing writes a `---` or a `...` a reader would have to ignore.
result<void> write_document(sink& out, const value& document) {
    yaml_event_t event;
    yaml_stream_start_event_initialize(&event, YAML_UTF8_ENCODING);
    if (!out.emit(event)) {
        return std::unexpected(out.problem());
    }
    yaml_document_start_event_initialize(&event, nullptr, nullptr, nullptr, 1);
    if (!out.emit(event)) {
        return std::unexpected(out.problem());
    }
    const result<void> written = write_node(out, document);
    if (!written.has_value()) {
        return written;
    }
    yaml_document_end_event_initialize(&event, 1);
    if (!out.emit(event)) {
        return std::unexpected(out.problem());
    }
    yaml_stream_end_event_initialize(&event);
    if (!out.emit(event)) {
        return std::unexpected(out.problem());
    }
    return {};
}

}  // namespace

result<value> yaml_codec::decode(std::string_view bytes) const {
    stream in(bytes);
    if (!in.next()) {
        return std::unexpected(in.problem());
    }
    if (!in.next()) {
        return std::unexpected(in.problem());
    }
    // A file holding nothing at all is a document holding nothing at all.
    if (in.at().type == YAML_STREAM_END_EVENT) {
        return value::null();
    }
    if (!in.next()) {
        return std::unexpected(in.problem());
    }
    anchors seen;
    result<value> document = read_node(in, seen);
    if (!document.has_value()) {
        return document;
    }
    const result<void> ended = read_to_end(in);
    if (!ended.has_value()) {
        return std::unexpected(ended.error());
    }
    return document;
}

result<std::string> yaml_codec::encode(const value& document) const {
    std::string out;
    sink into(&out);
    const result<void> written = write_document(into, document);
    if (!written.has_value()) {
        return std::unexpected(written.error());
    }
    return out;
}

const codec& yaml() {
    static const yaml_codec one;
    return one;
}

}  // namespace wrench
