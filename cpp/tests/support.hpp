// What the suites share: a real directory to work in.
//
// Nothing here stands in for the pack. A test that wants a file writes one with
// the standard library and hands the code under test a real path, so the
// shipped reader and writer are exercised against a filesystem rather than
// against something shaped like one. The seams exist for a test that wants no
// filesystem at all, and such a test derives from them itself.
#pragma once

#include <cstddef>
#include <filesystem>
#include <string>
#include <string_view>

namespace wrench::test {

// A directory created fresh under the system temporary directory and removed,
// with everything in it, when this goes out of scope.
class scratch {
   public:
    scratch();
    ~scratch();

    scratch(const scratch&) = delete;
    scratch& operator=(const scratch&) = delete;
    scratch(scratch&&) = delete;
    scratch& operator=(scratch&&) = delete;

    [[nodiscard]] const std::filesystem::path& path() const;

    // path/relative, with nothing created.
    [[nodiscard]] std::filesystem::path at(std::string_view relative) const;

    // Writes body to path/relative with the standard library, not with the
    // pack, and returns where it went. The two parameters are different types
    // so that a call cannot pass them the wrong way round.
    [[nodiscard]] std::filesystem::path put(const std::filesystem::path& relative,
                                            std::string_view body) const;

   private:
    std::filesystem::path path_;
};

// The whole of a file, read with the standard library, so a test asserting what
// the writer left behind does not read it back through the pack.
[[nodiscard]] std::string slurp(const std::filesystem::path& path);

// How many entries a directory holds, which is how a test asks whether a
// temporary was left behind.
[[nodiscard]] std::size_t entries(const std::filesystem::path& directory);

}  // namespace wrench::test
