#include "wrench/io.hpp"

#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <cerrno>
#include <cstddef>
#include <cstdlib>
#include <expected>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include <string_view>
#include <system_error>
#include <utility>

#include "wrench/error.hpp"

namespace wrench {

namespace {

// What a file this writer creates is left readable as. The other packs set the
// same, so a file one pack writes is a file another pack's consumer can read.
constexpr ::mode_t file_mode = 0644;

// What the last system call complained about. std::generic_category is the one
// that carries errno values, so the code compares equal to the std::errc a
// caller names.
std::error_code last_error() { return {errno, std::generic_category()}; }

// A failure naming the step, what was being attempted, and on which file.
//
// The reader and the writer are the two seams that know a path, so they are the
// two that put one in a message. A codec is handed bytes and never learns which
// file they came from.
failure io_failure(step which,
                   std::string_view doing,
                   const std::filesystem::path& path,
                   std::error_code cause) {
    std::string message(doing);
    message += ' ';
    message += path.string();
    message += ": ";
    message += cause.message();
    return failure{.step = which, .message = std::move(message), .cause = cause};
}

// The temporary file, removed unless the rename took it away.
//
// It holds the name by reference and allocates nothing, which is what makes it
// safe here: an allocation failure between creating the temporary and renaming
// it would otherwise leave the file behind, and this runs on that path too.
class temporary {
   public:
    explicit temporary(const std::string& path) : path_(path) {}

    ~temporary() {
        if (kept_) {
            return;
        }
        std::error_code ignored;
        std::filesystem::remove(path_, ignored);
    }

    temporary(const temporary&) = delete;
    temporary& operator=(const temporary&) = delete;
    temporary(temporary&&) = delete;
    temporary& operator=(temporary&&) = delete;

    // The file is where it belongs now, so leave it alone.
    void keep() { kept_ = true; }

   private:
    const std::string& path_;
    bool kept_ = false;
};

// Every byte to the descriptor, then the descriptor closed, whichever way it
// goes.
//
// The loop is not decoration: a write is allowed to be short, and treating one
// as complete is how a file ends up truncated with nothing reporting it. The
// close is checked for the same reason, because an error deferred by the
// operating system surfaces there and nowhere else.
std::error_code pour(int descriptor, std::string_view bytes) {
    const char* cursor = bytes.data();
    std::size_t remaining = bytes.size();
    while (remaining > 0) {
        const ssize_t written = ::write(descriptor, cursor, remaining);
        if (written < 0) {
            const std::error_code problem = last_error();
            ::close(descriptor);
            return problem;
        }
        cursor += written;
        remaining -= static_cast<std::size_t>(written);
    }
    if (::close(descriptor) != 0) {
        return last_error();
    }
    return {};
}

}  // namespace

reader::~reader() = default;

writer::~writer() = default;

result<std::string> local_file_reader::read(const std::filesystem::path& path) const {
    errno = 0;
    std::ifstream stream(path, std::ios::binary);
    if (!stream.is_open()) {
        return std::unexpected(io_failure(step::read, "reading", path, last_error()));
    }
    try {
        return std::string(std::istreambuf_iterator<char>(stream),
                           std::istreambuf_iterator<char>());
    } catch (const std::ios_base::failure& unreadable) {
        // A stream that cannot be read throws out of the buffer rather than
        // setting a flag, and a directory is the case that does it: it opens
        // successfully and fails on the first read. Catching it is what keeps
        // the failure inside wrench's own family.
        return std::unexpected(
            io_failure(step::read, "reading", path, unreadable.code()));
    }
}

result<void> local_file_writer::write(const std::filesystem::path& path,
                                      std::string_view bytes) const {
    // Beside the target, so the rename that follows stays inside one directory
    // and therefore one filesystem: a rename across filesystems is a copy, and
    // a copy is not atomic. Hidden, so a reader listing the directory between
    // the two steps does not take the temporary for a file of its own.
    std::string pattern =
        (path.parent_path() / ("." + path.filename().string() + ".XXXXXX")).string();
    errno = 0;
    const int descriptor = ::mkstemp(pattern.data());
    if (descriptor < 0) {
        return std::unexpected(io_failure(step::write, "writing", path, last_error()));
    }
    temporary written(pattern);

    if (const std::error_code unwritten = pour(descriptor, bytes)) {
        return std::unexpected(io_failure(step::write, "writing", path, unwritten));
    }

    // mkstemp creates the temporary readable by its owner alone, and a rename
    // carries that mode to the target, so a file written here would be private
    // where the same file written by another pack is not. The other three packs
    // set 0644 and a consumer reads what wrench wrote, so the mode is part of
    // what the packs agree on even though FR-6.3 states only the atomicity.
    errno = 0;
    if (::chmod(pattern.c_str(), file_mode) != 0) {
        return std::unexpected(io_failure(step::write, "writing", path, last_error()));
    }

    // The rename is the whole of the atomicity. Until it lands the target holds
    // what it held before, and afterwards it holds all of the new bytes, so a
    // concurrent reader never sees a partial file.
    std::error_code unrenamed;
    std::filesystem::rename(pattern, path, unrenamed);
    if (unrenamed) {
        return std::unexpected(io_failure(step::write, "writing", path, unrenamed));
    }
    written.keep();
    return {};
}

}  // namespace wrench
