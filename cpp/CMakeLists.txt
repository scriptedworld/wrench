# The C++ pack. A library and its suite, and nothing that runs on its own.
#
# The compilation database is the gate's contract. toolbox's cpp-std-quality jig
# reads compile_commands.json for format, lint, analyse and headers, so it is
# exported on every configure and linked to this directory by `just cpp-profile`.
# Nothing on a C++ command line knows what a project compiles or against which
# include paths, which is why the database and not a glob is what the jig reads.

cmake_minimum_required(VERSION 3.28)
# C as well as C++: libyaml is a C library built from source below.
project(wrench LANGUAGES C CXX VERSION 0.1.0)

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

# ---- the libraries the pack binds -------------------------------------------
#
# Each at the tag `docs/DECISIONS/which-libraries-the-cpp-pack-binds.md` names,
# fetched rather than taken from a distribution, so what a consumer compiles
# against is what that decision says and not what a machine happens to hold.
#
# The fetch lands beside the source and not under `build/`, because
# `just cpp-profile` empties the build directory on every run and a pinned tree
# is not build output. Nothing in it is instrumented or analysed.

set(FETCHCONTENT_BASE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/.deps)
include(FetchContent)

# SYSTEM on every one of them, and it is load bearing rather than tidy. A
# third-party header reached through -I is a header the checkers report on:
# cppcheck --enable=all fails inside jsoncons with a missing return and an
# uninitialised member it found in template code the pack cannot edit, and
# -Wconversion has the same reach. Through -isystem the same run is clean.
FetchContent_Declare(
    libyaml
    GIT_REPOSITORY https://github.com/yaml/libyaml
    GIT_TAG 0.2.5
    GIT_SHALLOW TRUE
    SYSTEM
)
FetchContent_Declare(
    jsoncons
    GIT_REPOSITORY https://github.com/danielaparker/jsoncons
    GIT_TAG v1.9.0
    GIT_SHALLOW TRUE
    SYSTEM
)
FetchContent_Declare(
    doctest
    GIT_REPOSITORY https://github.com/doctest/doctest
    GIT_TAG v2.5.3
    GIT_SHALLOW TRUE
    SYSTEM
)

# jsoncons builds its own suite by default and that suite needs a framework this
# tree does not fetch, so the option is answered before the subdirectory is read.
set(JSONCONS_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
# libyaml 0.2.5 asks for compatibility with CMake 3.0, which CMake 3.31 no
# longer offers. The floor is raised for it rather than the pin being moved.
set(CMAKE_POLICY_VERSION_MINIMUM 3.5)

# The database describes what the pack compiles. libyaml's C sources are not
# that, and every analysis task walks the database, so they are kept out of it.
set(CMAKE_EXPORT_COMPILE_COMMANDS OFF)
FetchContent_MakeAvailable(libyaml jsoncons doctest)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# ---- the shipped schemas ----------------------------------------------------
#
# FR-3.7: the set comes from reading the directory, never from a list of
# filenames in the source. CONFIGURE_DEPENDS re-reads the glob on every build,
# so a schema added or removed reaches the pack; the custom command's DEPENDS
# catches one edited.

set(WRENCH_SCHEMA_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../schemas)
file(GLOB WRENCH_SCHEMA_FILES CONFIGURE_DEPENDS ${WRENCH_SCHEMA_DIR}/*.schema.json)

set(WRENCH_GENERATED_DIR ${CMAKE_CURRENT_BINARY_DIR}/generated)
set(WRENCH_SHIPPED_HEADER ${WRENCH_GENERATED_DIR}/wrench/shipped.hpp)

add_custom_command(
    OUTPUT ${WRENCH_SHIPPED_HEADER}
    COMMAND ${CMAKE_COMMAND} -E make_directory ${WRENCH_GENERATED_DIR}/wrench
    COMMAND ${CMAKE_COMMAND}
            "-DWRENCH_SCHEMA_FILES=${WRENCH_SCHEMA_FILES}"
            -DWRENCH_SHIPPED_HEADER=${WRENCH_SHIPPED_HEADER}
            -P ${CMAKE_CURRENT_SOURCE_DIR}/cmake/generate-shipped.cmake
    DEPENDS ${WRENCH_SCHEMA_FILES} ${CMAKE_CURRENT_SOURCE_DIR}/cmake/generate-shipped.cmake
    COMMENT "reading the shipped schemas out of schemas/"
    VERBATIM
)
add_custom_target(wrench-shipped DEPENDS ${WRENCH_SHIPPED_HEADER})

# ---- the library ------------------------------------------------------------

add_library(wrench STATIC
    src/canonical.cpp
    src/codec.cpp
    src/error.cpp
    src/file.cpp
    src/io.cpp
    src/json_codec.cpp
    src/schema.cpp
    src/yaml_codec.cpp
)
# The alias is the name a consumer writes, whether it reached this pack through
# FetchContent or through find_package, so the two spellings never differ.
add_library(wrench::wrench ALIAS wrench)
add_dependencies(wrench wrench-shipped)

# BUILD_INTERFACE and INSTALL_INTERFACE rather than a bare path, so an installed
# package exports an include directory that exists on the consumer's machine.
target_include_directories(wrench PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)
# The generated header is a system directory for the reason the fetched trees
# are: nothing in it is written by hand, so no checker should report on it.
target_include_directories(wrench SYSTEM PRIVATE
    $<BUILD_INTERFACE:${WRENCH_GENERATED_DIR}>
)
target_compile_features(wrench PUBLIC cxx_std_23)

# jsoncons is public because `wrench::value` is `jsoncons::json`, so a consumer
# compiles against its headers. libyaml is private: the YAML codec is the only
# thing that knows it exists.
target_link_libraries(wrench PUBLIC jsoncons)
target_link_libraries(wrench PRIVATE yaml)

# cppcheck has no compiler builtins, so jsoncons's endian probe reaches its own
# `#error "Unable to determine byte order!"` and the analyse task fails inside a
# header. The answer is the one CMake already worked out for this platform, so
# nothing here is hard-coded to a byte order.
target_compile_definitions(wrench PRIVATE
    $<$<STREQUAL:${CMAKE_CXX_BYTE_ORDER},LITTLE_ENDIAN>:_LITTLE_ENDIAN>
    $<$<STREQUAL:${CMAKE_CXX_BYTE_ORDER},BIG_ENDIAN>:_BIG_ENDIAN>
)

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

# ---- the suite --------------------------------------------------------------
#
# Built when this is the project being worked on, and not when the pack has been
# pulled into somebody else's tree by FetchContent or add_subdirectory. A
# consumer asking for the library should not be made to resolve doctest.

if(PROJECT_IS_TOP_LEVEL)
    add_executable(wrench-tests
        tests/allocation.cpp
        tests/canonical_test.cpp
        tests/codec_test.cpp
        tests/file_test.cpp
        tests/io_test.cpp
        tests/main.cpp
        tests/schema_test.cpp
        tests/support.cpp
        tests/yaml_test.cpp
    )
    target_include_directories(wrench-tests PRIVATE tests)
    target_link_libraries(wrench-tests PRIVATE wrench doctest::doctest)
    target_compile_definitions(wrench-tests PRIVATE
        # The suite reads the schema directory itself, so FR-5.7 is checked
        # against the one authority rather than against the pack's own copy.
        WRENCH_SCHEMA_DIR="${WRENCH_SCHEMA_DIR}"
        # The fixture set lives beside the schemas (FR-5.6).
        WRENCH_TESTDATA_DIR="${CMAKE_CURRENT_SOURCE_DIR}/../testdata"
        $<$<STREQUAL:${CMAKE_CXX_BYTE_ORDER},LITTLE_ENDIAN>:_LITTLE_ENDIAN>
        $<$<STREQUAL:${CMAKE_CXX_BYTE_ORDER},BIG_ENDIAN>:_BIG_ENDIAN>
    )
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
