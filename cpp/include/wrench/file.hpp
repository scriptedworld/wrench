// The two calls, and the pair of wrappers per format.
//
// File handling is these two and nothing else (FR-2.1). Four arguments each, in
// the order the contract fixes, because the fixture set and the parity check
// compare packs against each other.
//
// Load reads, decodes, then validates. Save validates, encodes, then writes.
// Validation on the way out is not symmetry for its own sake (FR-2.4): it stops
// a caller writing a structure wrench would refuse to read back, so a file a
// save produced always survives a load.
//
// The schema cannot be omitted (FR-2.2). It can be wrong, and no part of the
// library detects that (FR-2.3).
//
// Every seam arrives as a reference, so this header names them and does not
// include them. A caller includes the ones it hands over: `wrench/schema.hpp`
// for a schema, `wrench/io.hpp` for the shipped reader and writer, and
// `wrench/codec.hpp` where it names a codec rather than using a wrapper.
#pragma once

#include <filesystem>

#include "wrench/error.hpp"
#include "wrench/value.hpp"

namespace wrench {

class codec;
class reader;
class schema;
class writer;

// Read the file, decode it, and check the structure against the schema.
//
// The failure names which step failed (FR-2.6) and carries the path. A codec is
// handed bytes and a schema a structure, so neither knows which file it is
// working on and the path is filled in here.
[[nodiscard]] result<value> load_formatted_file(const std::filesystem::path& path,
                                                const schema& against,
                                                const codec& format,
                                                const reader& source);

// Check the structure, encode it in canonical form, and put the bytes in place.
[[nodiscard]] result<void> save_formatted_file(const value& document,
                                               const std::filesystem::path& path,
                                               const schema& against,
                                               const codec& format,
                                               const writer& sink);

// The wrappers supply the codec and add nothing else (FR-2.10). Validation stays
// in the core call, so the seam is unchanged in both directions, and the codec is
// named rather than inferred from the file's suffix: choosing a parser by
// filename would make behaviour depend on what a file is called, and renaming
// one would silently change how it is read.

[[nodiscard]] result<value> load_yaml_file(const std::filesystem::path& path,
                                           const schema& against,
                                           const reader& source);

[[nodiscard]] result<void> save_yaml_file(const value& document,
                                          const std::filesystem::path& path,
                                          const schema& against,
                                          const writer& sink);

[[nodiscard]] result<value> load_json_file(const std::filesystem::path& path,
                                           const schema& against,
                                           const reader& source);

[[nodiscard]] result<void> save_json_file(const value& document,
                                          const std::filesystem::path& path,
                                          const schema& against,
                                          const writer& sink);

}  // namespace wrench
