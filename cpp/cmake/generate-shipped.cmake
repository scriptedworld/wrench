# The shipped schemas, read out of the directory and written as a header.
#
# FR-3.7 asks a pack to discover the schemas by reading the directory rather
# than from a list of filenames in its own source, and FR-3.2 asks that what a
# pack carries is the one copy in `schemas/` rather than a second copy free to
# drift from it. No compiler here can read a directory, so the reading happens
# in a generator, as Rust's `build.rs` does.
#
# Run at build time, not configure time, with the schema files as dependencies:
# a file(GLOB CONFIGURE_DEPENDS in CMakeLists.txt catches a schema added or
# removed, and this catches a schema edited.
#
#     cmake -DWRENCH_SCHEMA_FILES=<list> -DWRENCH_SHIPPED_HEADER=<path>
#           -P generate-shipped.cmake
#
# The bytes are escaped into ordinary string literals rather than wrapped in a
# raw literal. A raw literal needs a delimiter that does not appear in the
# content, which is a property of the content nobody is checking.

cmake_minimum_required(VERSION 3.28)

if(NOT DEFINED WRENCH_SCHEMA_FILES OR NOT DEFINED WRENCH_SHIPPED_HEADER)
    message(FATAL_ERROR "generate-shipped: WRENCH_SCHEMA_FILES and WRENCH_SHIPPED_HEADER are both required")
endif()

if(WRENCH_SCHEMA_FILES STREQUAL "")
    message(FATAL_ERROR "generate-shipped: the schema directory holds no .schema.json file")
endif()

set(entries "")
set(count 0)

foreach(path IN LISTS WRENCH_SCHEMA_FILES)
    get_filename_component(leaf "${path}" NAME)
    string(REGEX REPLACE "\\.schema\\.json$" "" stem "${leaf}")

    file(READ "${path}" text)

    # Order matters: the backslashes are doubled before the quotes gain one, or
    # the escape this adds would itself be escaped.
    string(REPLACE "\\" "\\\\" text "${text}")
    string(REPLACE "\"" "\\\"" text "${text}")
    # One literal per line of the file, concatenated by the compiler, so the
    # generated header is diffable and no line is thousands of characters long.
    string(REPLACE "\n" "\\n\"\n            \"" text "${text}")

    string(APPEND entries "    wrench::shipped::document{\n")
    string(APPEND entries "        .stem = \"${stem}\",\n")
    string(APPEND entries "        .text =\n")
    string(APPEND entries "            \"${text}\",\n")
    string(APPEND entries "    },\n")
    math(EXPR count "${count} + 1")
endforeach()

set(header "// The shipped schemas, generated from the directory they live in.\n")
string(APPEND header "//\n")
string(APPEND header "// Written by cpp/cmake/generate-shipped.cmake on every build whose schema\n")
string(APPEND header "// directory has changed. Nothing here is edited by hand and nothing here is\n")
string(APPEND header "// committed, so no copy of a schema can go stale against `schemas/`.\n")
string(APPEND header "#pragma once\n")
string(APPEND header "\n")
string(APPEND header "#include <array>\n")
string(APPEND header "#include <string_view>\n")
string(APPEND header "\n")
string(APPEND header "namespace wrench::shipped {\n")
string(APPEND header "\n")
string(APPEND header "// One schema: the name its file carries, and the bytes of that file.\n")
string(APPEND header "// The `$id` is not repeated here; it is read from the document itself,\n")
string(APPEND header "// which is what FR-3.6 names a schema by.\n")
string(APPEND header "struct document {\n")
string(APPEND header "    std::string_view stem;\n")
string(APPEND header "    std::string_view text;\n")
string(APPEND header "};\n")
string(APPEND header "\n")
string(APPEND header "inline constexpr std::array<document, ${count}> documents{{\n")
string(APPEND header "${entries}")
string(APPEND header "}};\n")
string(APPEND header "\n")
string(APPEND header "}  // namespace wrench::shipped\n")

# Written through a temporary and compared, so an unchanged header keeps its
# timestamp and does not rebuild the pack.
file(WRITE "${WRENCH_SHIPPED_HEADER}.new" "${header}")
execute_process(
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${WRENCH_SHIPPED_HEADER}.new" "${WRENCH_SHIPPED_HEADER}"
)
file(REMOVE "${WRENCH_SHIPPED_HEADER}.new")
