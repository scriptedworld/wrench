// What a decoder produces and an encoder is handed.
//
// FR-2.9 fixes the model: maps, lists, and the JSON scalars of string, number,
// boolean and null, with a string for every map key. `jsoncons::json` is that
// model exactly, so the pack names it rather than wrapping it.
//
// Two things follow, and both are why the alias is the choice here. A value
// reaching the validate step is already the validator's own type, so a load
// pays for no second representation of the document; and the key sorting
// canonical form asks for is a property of the type, `jsoncons::json` keeping
// its members ordered by key, so the first of the four adapters costs no code.
//
// The cost is that the pack's surface names a bound library's type. A consumer
// writes `jsoncons::json` under the alias, and binding a different validator
// later would be a breaking change to every call site rather than an internal
// one. `docs/DECISIONS/which-libraries-the-cpp-pack-binds.md` carries why
// validation cannot be a library of its own in this language, which is what
// makes that trade the cheaper of the two.
#pragma once

#include <jsoncons/basic_json.hpp>

namespace wrench {

// The value model, in the one type the codecs and the validator share.
using value = jsoncons::json;

}  // namespace wrench
