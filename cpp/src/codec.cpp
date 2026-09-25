#include "wrench/codec.hpp"

namespace wrench {

// Out of line for the reason `reader`'s and `writer`'s are: a defaulted
// destructor in the header is emitted into every translation unit that includes
// it and the linker keeps whichever copy it likes, so the one a coverage build
// instruments is not the one that runs.
codec::~codec() = default;

}  // namespace wrench
