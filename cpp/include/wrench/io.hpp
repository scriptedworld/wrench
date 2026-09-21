// The two IO seams and the pair that ships.
//
// The codec is the format and the reader or writer is the IO, declared
// separately (FR-2.5), so a format is added without inventing a source and a
// source without inventing a format. A reader is handed the path and not the
// bytes (FR-2.5a): handed bytes it would put the open at the call site, and a
// substituted reader would then be replacing the parse alone.
//
// One reader and one writer ship, both local files, and nothing else (FR-2.8).
// A test brings its own by deriving from the seam, which is what the seam is
// for.
#pragma once

#include <filesystem>
#include <string>
#include <string_view>

#include "wrench/error.hpp"

namespace wrench {

// The IO on the way in. Knows nothing about the format of what it reads.
// The destructors are defined in io.cpp rather than defaulted here. A
// defaulted one is emitted into every translation unit that includes this
// header, and the linker keeps whichever copy it likes, so the one the coverage
// build instruments is not the one that runs. Out of line there is one
// definition, it is measured, and a seam destroyed anywhere counts.
class reader {
   public:
    virtual ~reader();

    // The whole contents of path, or why they could not be had.
    [[nodiscard]] virtual result<std::string> read(
        const std::filesystem::path& path) const = 0;

   protected:
    // Protected rather than deleted: a seam is held by reference and copied
    // only by whatever derives from it, which is the deriving class's business.
    reader() = default;
    reader(const reader&) = default;
    reader(reader&&) = default;
    reader& operator=(const reader&) = default;
    reader& operator=(reader&&) = default;
};

// The IO on the way out. Puts the whole contents in place, or none of them.
class writer {
   public:
    virtual ~writer();

    [[nodiscard]] virtual result<void> write(const std::filesystem::path& path,
                                             std::string_view bytes) const = 0;

   protected:
    writer() = default;
    writer(const writer&) = default;
    writer(writer&&) = default;
    writer& operator=(const writer&) = default;
    writer& operator=(writer&&) = default;
};

// The shipped reader: a file on the machine the process is running on.
class local_file_reader final : public reader {
   public:
    [[nodiscard]] result<std::string> read(
        const std::filesystem::path& path) const override;
};

// The shipped writer, and it is atomic (FR-6.3).
//
// The bytes go to a temporary file beside the target and are renamed into
// place, so a concurrent reader sees the previous contents or the new ones and
// never a half-written file. Beside the target and not in the system temporary
// directory, because a rename across filesystems is a copy and a copy is not
// atomic.
class local_file_writer final : public writer {
   public:
    [[nodiscard]] result<void> write(const std::filesystem::path& path,
                                     std::string_view bytes) const override;
};

}  // namespace wrench
