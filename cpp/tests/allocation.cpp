#include "allocation.hpp"

#include <cstddef>
#include <cstdlib>
#include <functional>
#include <new>

namespace {

// Allocations left before the armed one fails, negative being disarmed. Per
// thread, so a library thread is never failed by a test on another.
thread_local std::ptrdiff_t countdown = -1;
thread_local bool fired_here = false;

// Whether this allocation is the armed one, consuming the arming if it is.
bool should_fail() {
    if (countdown < 0) {
        return false;
    }
    if (countdown == 0) {
        countdown = -1;
        fired_here = true;
        return true;
    }
    --countdown;
    return false;
}

// A zero-byte request still returns a unique pointer, as the default does.
std::size_t at_least_one(std::size_t size) { return size == 0 ? 1 : size; }

void* plain(std::size_t size) {
    if (should_fail()) {
        return nullptr;
    }
    return std::malloc(at_least_one(size));
}

void* or_throw(void* allocated) {
    if (allocated == nullptr) {
        throw std::bad_alloc();
    }
    return allocated;
}

}  // namespace

// The replacements. The aligned forms are left to the default: nothing in this
// pack allocates an over-aligned type, and a form that is never armed would be
// a branch nothing reaches.
void* operator new(std::size_t size) { return or_throw(plain(size)); }

void* operator new[](std::size_t size) { return or_throw(plain(size)); }

void* operator new(std::size_t size, const std::nothrow_t& /*tag*/) noexcept {
    return plain(size);
}

void* operator new[](std::size_t size, const std::nothrow_t& /*tag*/) noexcept {
    return plain(size);
}

// Replaced alongside, so what malloc returned is what free is handed rather
// than resting on the default deallocation happening to agree.
void operator delete(void* pointer) noexcept { std::free(pointer); }

void operator delete[](void* pointer) noexcept { std::free(pointer); }

void operator delete(void* pointer, std::size_t /*size*/) noexcept {
    std::free(pointer);
}

void operator delete[](void* pointer, std::size_t /*size*/) noexcept {
    std::free(pointer);
}

void operator delete(void* pointer, const std::nothrow_t& /*tag*/) noexcept {
    std::free(pointer);
}

void operator delete[](void* pointer, const std::nothrow_t& /*tag*/) noexcept {
    std::free(pointer);
}

namespace wrench::test {

failing_allocation::failing_allocation(std::size_t after) {
    countdown = static_cast<std::ptrdiff_t>(after);
    fired_here = false;
}

failing_allocation::~failing_allocation() { countdown = -1; }

bool failing_allocation::fired() { return fired_here; }

sweep fail_each_allocation(const std::function<void()>& body) {
    // Far above any body a suite here hands this, and low enough that a body
    // allocating without end fails the sweep instead of hanging the run.
    constexpr std::size_t limit = 100000;
    sweep found;
    for (std::size_t armed = 0; armed < limit; ++armed) {
        bool thrown = false;
        bool reached = false;
        {
            const failing_allocation failure(armed);
            try {
                body();
            } catch (const std::bad_alloc&) {
                thrown = true;
            }
            reached = failing_allocation::fired();
        }
        if (!reached) {
            found.completed = true;
            break;
        }
        if (thrown) {
            ++found.thrown;
        } else {
            ++found.absorbed;
        }
    }
    return found;
}

}  // namespace wrench::test
