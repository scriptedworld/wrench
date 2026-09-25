#include "wrench/error.hpp"

#include <string_view>
#include <utility>

namespace wrench {

std::string_view name(step which) {
    switch (which) {
        case step::read:
            return "read";
        case step::parse:
            return "parse";
        case step::schema:
            return "schema";
        case step::validate:
            return "validate";
        case step::encode:
            return "encode";
        case step::write:
            return "write";
    }
    // Every enumerator is answered above, so there is nothing after the switch
    // for a well-formed value to reach.
    std::unreachable();
}

}  // namespace wrench
