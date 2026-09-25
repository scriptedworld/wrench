// What a failure is here, and how a caller receives one.
//
// FR-2.11 makes every failure crossing the boundary wrench's own type carrying
// the cause, and FR-2.6 makes it name which step failed. Six kinds ship. The
// seventh, `usage`, is absent by the same argument Rust omits it under: the
// seams arrive as references, so a call naming no schema, codec, reader or
// writer does not compile and there is no run-time state to report.
//
// The answer is std::expected and not an exception, because a file that is not
// there and a value with no canonical form are results a caller is expected to
// handle rather than faults in the program. An allocation failure is the one
// thing that still leaves through a throw: reporting it would mean building a
// message, which allocates.
#pragma once

#include <cstdint>
#include <expected>
#include <string>
#include <string_view>
#include <system_error>

namespace wrench {

// Which step failed. The enumerators are the contract's vocabulary, spelled
// identically in every pack, and a consumer matches on them rather than on the
// message.
//
// They pair on three axes, which is what makes them worth separating:
// read against write is the IO, parse against encode is the conversion, and
// schema against validate is whether the schema or the document is at fault.
enum class step : std::uint8_t {
    read,
    parse,
    schema,
    validate,
    encode,
    write,
};

// The step as the word every pack spells it with, which is what a consumer
// writes into a reason's `kind`. The kinds are data and not only types, so
// reaching the word costs no switch at the call site.
[[nodiscard]] std::string_view name(step which);

// One failure: the step, a message for a person, and the cause underneath.
struct failure {
    wrench::step step;
    // wrench's own words, with what the bound library said appended where
    // there was anything. A codec is handed bytes and a schema a structure, so
    // neither knows which file it is working on; the two calls fill the path in
    // on the way out.
    std::string message;
    // Empty where nothing underneath produced a code, which is how a refusal
    // that is wrench's own judgement differs from an operating system error.
    // A bound library reports in prose rather than in codes, so its failures
    // reach a caller through the message and this stays empty.
    std::error_code cause;
};

// What every entry point answers with. `result<void>` is the shape for a call
// that produces nothing but can still fail.
template <typename T>
using result = std::expected<T, failure>;

}  // namespace wrench
