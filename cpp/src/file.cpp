#include "wrench/file.hpp"

#include <expected>
#include <filesystem>
#include <string>
#include <string_view>
#include <utility>

#include "wrench/codec.hpp"
#include "wrench/error.hpp"
#include "wrench/io.hpp"
#include "wrench/schema.hpp"
#include "wrench/value.hpp"

namespace wrench {

namespace {

// What was being attempted, for the step that failed.
//
// A reader and a writer are handed the path, so they name the file themselves
// and never arrive here. The other four seams are handed bytes or a value, so
// the file is theirs to be told about rather than to know.
std::string_view doing(step which) {
    if (which == step::parse) {
        return "parsing";
    }
    if (which == step::schema) {
        return "the schema for";
    }
    if (which == step::encode) {
        return "encoding";
    }
    return "validating";
}

// The same failure with the file named in it, so a consumer unwraps once to
// reach the cause and does not have to remember which call it made.
failure named(failure held, const std::filesystem::path& path) {
    std::string message(doing(held.step));
    message += ' ';
    message += path.string();
    message += ": ";
    message += held.message;
    held.message = std::move(message);
    return held;
}

}  // namespace

result<value> load_formatted_file(const std::filesystem::path& path,
                                  const schema& against,
                                  const codec& format,
                                  const reader& source) {
    const result<std::string> bytes = source.read(path);
    if (!bytes.has_value()) {
        return std::unexpected(bytes.error());
    }
    result<value> document = format.decode(*bytes);
    if (!document.has_value()) {
        return std::unexpected(named(document.error(), path));
    }
    const result<void> matched = against.validate(*document);
    if (!matched.has_value()) {
        return std::unexpected(named(matched.error(), path));
    }
    return document;
}

result<void> save_formatted_file(const value& document,
                                 const std::filesystem::path& path,
                                 const schema& against,
                                 const codec& format,
                                 const writer& sink) {
    // Validation first, so a structure wrench would refuse to read back is never
    // written at all (FR-2.4). Encoding a document that cannot be loaded would
    // leave the refusal to whoever reads it next.
    const result<void> matched = against.validate(document);
    if (!matched.has_value()) {
        return std::unexpected(named(matched.error(), path));
    }
    const result<std::string> bytes = format.encode(document);
    if (!bytes.has_value()) {
        return std::unexpected(named(bytes.error(), path));
    }
    return sink.write(path, *bytes);
}

result<value> load_yaml_file(const std::filesystem::path& path,
                             const schema& against,
                             const reader& source) {
    return load_formatted_file(path, against, yaml(), source);
}

result<void> save_yaml_file(const value& document,
                            const std::filesystem::path& path,
                            const schema& against,
                            const writer& sink) {
    return save_formatted_file(document, path, against, yaml(), sink);
}

result<value> load_json_file(const std::filesystem::path& path,
                             const schema& against,
                             const reader& source) {
    return load_formatted_file(path, against, json(), source);
}

result<void> save_json_file(const value& document,
                            const std::filesystem::path& path,
                            const schema& against,
                            const writer& sink) {
    return save_formatted_file(document, path, against, json(), sink);
}

}  // namespace wrench
