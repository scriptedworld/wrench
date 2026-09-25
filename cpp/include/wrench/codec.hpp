// The format seam, and the two codecs that ship.
//
// A codec is the format and nothing else (FR-2.5). It is handed bytes or a
// value and never a path, so it cannot name the file it is working on, and the
// two calls are what put the path into a failure.
//
// `encode` emits canonical form (FR-4.3), so a caller cannot ask for a valid
// document written another way. The four adapters are what canonical form is
// made of, and each codec applies all four: keys sorted, every string and key
// quoted where the format has quoting, floats spelled positionally, and null
// written as the word.
#pragma once

#include <string>
#include <string_view>

#include "wrench/error.hpp"
#include "wrench/value.hpp"

namespace wrench {

// One format, both directions.
//
// The destructor is defined out of line for the reason `reader`'s is: a
// defaulted one lands in every translation unit that includes this header and
// the linker keeps whichever copy it likes, so the one a coverage build
// instruments is not the one that runs.
class codec {
   public:
    virtual ~codec();

    // Bytes to a value in the model FR-2.9 fixes. A format's own types are
    // reconciled here: a spelling that carries the value whole becomes a
    // string, and a key that is not a string is refused.
    [[nodiscard]] virtual result<value> decode(std::string_view bytes) const = 0;

    // A value to the format's canonical bytes, or a refusal where the value has
    // no canonical form.
    [[nodiscard]] virtual result<std::string> encode(const value& document) const = 0;

   protected:
    codec() = default;
    codec(const codec&) = default;
    codec(codec&&) = default;
    codec& operator=(const codec&) = default;
    codec& operator=(codec&&) = default;
};

// YAML, in block style with every string quoted (FR-4.1, FR-4.4).
class yaml_codec final : public codec {
   public:
    [[nodiscard]] result<value> decode(std::string_view bytes) const override;
    [[nodiscard]] result<std::string> encode(const value& document) const override;
};

// JSON, two-space indented with sorted keys and a trailing newline (FR-4.6).
class json_codec final : public codec {
   public:
    [[nodiscard]] result<value> decode(std::string_view bytes) const override;
    [[nodiscard]] result<std::string> encode(const value& document) const override;
};

// The shipped instances, as the other packs expose them. A codec holds no
// state, so one of each is all there is to have.
[[nodiscard]] const codec& yaml();
[[nodiscard]] const codec& json();

}  // namespace wrench
