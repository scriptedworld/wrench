// Allocation that fails on demand, for the suites and nothing else.
//
// allocation.cpp replaces the global operator new and delete in the test binary
// only; nothing a consumer links carries it. Every replacement allocates exactly
// as the default does until a failure is armed, and then the allocation it names
// fails once: the throwing forms throw std::bad_alloc and the nothrow forms
// return nullptr.
//
// It exists because gcov counts the edge every allocating call takes when it
// throws, and those edges count against the branch minimum the C++ jig enforces.
// Nothing a test can hand the pack makes an allocation fail, so without this the
// only ways to reach them would be to exclude them from the measurement or to
// stop measuring branches, and both are refused. Registered in SUPPRESSIONS with
// the question that was asked and the answer given.
#pragma once

#include <cstddef>
#include <functional>

namespace wrench::test {

// Arms the allocation `after` allocations from now, 0 being the next one, to
// fail on this thread, until it fires or this goes out of scope.
class failing_allocation {
   public:
    explicit failing_allocation(std::size_t after);
    ~failing_allocation();

    failing_allocation(const failing_allocation&) = delete;
    failing_allocation& operator=(const failing_allocation&) = delete;
    failing_allocation(failing_allocation&&) = delete;
    failing_allocation& operator=(failing_allocation&&) = delete;

    // Whether the allocation armed on this thread was reached and failed.
    [[nodiscard]] static bool fired();
};

// What running a body once per allocation it makes found.
struct sweep {
    // Runs where the failed allocation left the body as a std::bad_alloc.
    std::size_t thrown = 0;
    // Runs where an allocation failed and the body returned anyway, which a
    // nothrow allocation or a caught failure produces.
    std::size_t absorbed = 0;
    // Whether a run finally made every allocation it wanted and completed.
    // False means the sweep stopped at its limit first, which is a body that
    // allocates without end rather than a result.
    bool completed = false;
};

// Runs body with its first allocation failing, then its second, and so on,
// until a run completes without reaching the armed one. Every allocating call
// in the body therefore takes its throwing edge once.
sweep fail_each_allocation(const std::function<void()>& body);

}  // namespace wrench::test
