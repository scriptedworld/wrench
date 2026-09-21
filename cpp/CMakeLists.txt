# The C++ pack. A library and its suite, and nothing that runs on its own.
#
# The compilation database is the gate's contract. toolbox's cpp-std-quality jig
# reads compile_commands.json for format, lint, analyse and headers, so it is
# exported on every configure and linked to this directory by `just cpp-profile`.
# Nothing on a C++ command line knows what a project compiles or against which
# include paths, which is why the database and not a glob is what the jig reads.

cmake_minimum_required(VERSION 3.28)
project(wrench LANGUAGES CXX VERSION 0.1.0)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# No compiler extensions: the pack is written to the standard, and a GNU
# extension that compiles here would be a surprise to a consumer on another
# compiler.
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
# Nothing here is a module, and scanning for them adds a dyndep step per target.
set(CMAKE_CXX_SCAN_FOR_MODULES OFF)

# Coverage is a build of its own. gcov's instrumentation is what the jig's
# `tests` task reads, and it must never reach a build a consumer links.
option(WRENCH_COVERAGE "instrument the library for gcov" OFF)

find_package(doctest REQUIRED)

add_library(wrench STATIC
    src/canonical.cpp
    src/io.cpp
)
# The alias is the name a consumer writes, whether it reached this pack through
# FetchContent or through find_package, so the two spellings never differ.
add_library(wrench::wrench ALIAS wrench)

# BUILD_INTERFACE and INSTALL_INTERFACE rather than a bare path, so an installed
# package exports an include directory that exists on the consumer's machine.
target_include_directories(wrench PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
target_compile_features(wrench PUBLIC cxx_std_23)

# The warning set is the pack's first checker and runs before any of the jig's.
# -Werror is what makes it one: a warning nobody is made to read is a warning
# that accumulates.
target_compile_options(wrench PRIVATE
    -Wall
    -Wextra
    -Wpedantic
    -Wconversion
    -Wsign-conversion
    -Wshadow
    -Werror
)

# The code under test is instrumented and the tests are not. A doctest assertion
# expands to branches taken only when it fails, so an instrumented test file
# reports a large share of its branches untaken in a suite that passes. That
# figure measures the assertion macros and not anything a test could be missing.
if(WRENCH_COVERAGE)
    target_compile_options(wrench PRIVATE --coverage -O0)
    target_link_options(wrench PUBLIC --coverage)
endif()

# The suite is built when this is the project being worked on, and not when the
# pack has been pulled into somebody else's tree by FetchContent or
# add_subdirectory. A consumer asking for the library should not be made to
# resolve doctest.
if(PROJECT_IS_TOP_LEVEL)
    add_executable(wrench-tests
        tests/allocation.cpp
        tests/canonical_test.cpp
        tests/io_test.cpp
        tests/main.cpp
        tests/support.cpp
    )
    target_include_directories(wrench-tests PRIVATE tests)
    target_link_libraries(wrench-tests PRIVATE wrench doctest::doctest)
    target_compile_options(wrench-tests PRIVATE
        -Wall
        -Wextra
        -Wpedantic
        -Wconversion
        -Wsign-conversion
        -Wshadow
        -Werror
    )
endif()
