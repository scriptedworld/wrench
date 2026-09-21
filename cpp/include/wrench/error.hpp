// What a failure is here, and how a caller receives one.
//
// FR-2.11 makes every failure crossing the boundary wrench's own type carrying
// the cause, and FR-2.6 makes it name which step failed. The family has seven
// kinds. Three of them are reachable from a float spelling, a local file reader
// and a local file writer, so three are declared and the rest arrive with the
// codecs and the two calls.
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
#include <system_error>

namespace wrench {

// Which step failed. The enumerators are the contract's vocabulary, spelled
// identically in every pack, and a consumer matches on them rather than on the
// message.
enum class step : std::uint8_t {
    read,
    encode,
    write,
};

// One failure: the step, a message for a person, and the cause underneath.
struct failure {
    wrench::step step;
    std::string message;
    // Empty where nothing underneath produced a code, which is how a refusal
    // that is wrench's own judgement differs from an operating system error.
    std::error_code cause;
};

// What every entry point answers with. `result<void>` is the shape for a call
// that produces nothing but can still fail.
template <typename T>
using result = std::expected<T, failure>;

}  // namespace wrench
