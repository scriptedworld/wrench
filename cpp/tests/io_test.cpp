// The two IO seams and the pair that ships: FR-2.5, FR-2.5a, FR-2.8 and the
// atomic write of FR-6.3.
#include "wrench/io.hpp"

#include <doctest/doctest.h>

#include <filesystem>
#include <functional>
#include <ostream>
#include <string>
#include <string_view>
#include <system_error>
#include <utility>

#include "allocation.hpp"
#include "support.hpp"
#include "wrench/error.hpp"

namespace {

// A reader that answers from memory and opens nothing. This is what FR-2.5a is
// for: handed the path rather than the bytes, a substitute stands where the
// filesystem would be, and a caller above it is exercised against no filesystem
// at all.
class canned_reader final : public wrench::reader {
   public:
    explicit canned_reader(std::string bytes) : bytes_(std::move(bytes)) {}

    [[nodiscard]] wrench::result<std::string> read(
        const std::filesystem::path& path) const override {
        asked_ = path;
        return bytes_;
    }

    [[nodiscard]] const std::filesystem::path& asked() const { return asked_; }

   private:
    std::string bytes_;
    mutable std::filesystem::path asked_;
};

// A writer that keeps what it was handed, for the same reason.
class recording_writer final : public wrench::writer {
   public:
    [[nodiscard]] wrench::result<void> write(const std::filesystem::path& path,
                                             std::string_view bytes) const override {
        asked_ = path;
        kept_ = bytes;
        return {};
    }

    [[nodiscard]] const std::filesystem::path& asked() const { return asked_; }

    [[nodiscard]] const std::string& kept() const { return kept_; }

   private:
    mutable std::filesystem::path asked_;
    mutable std::string kept_;
};

// The two calls will hold the seams by reference, so the suite does too: a test
// that passes only against the concrete type says nothing about the seam.
std::string through(const wrench::reader& seam, const std::filesystem::path& path) {
    const auto bytes = seam.read(path);
    REQUIRE(bytes.has_value());
    return *bytes;
}

}  // namespace

// COVERS: FR-2.8 | positive
TEST_CASE("the shipped reader gives back what is on disk") {
    const wrench::test::scratch area;
    const std::filesystem::path file = area.put("carried.yaml", "one: 1\n");

    CHECK(through(wrench::local_file_reader(), file) == "one: 1\n");
}

// COVERS: FR-2.8 | edge
TEST_CASE("an empty file reads back as no bytes rather than as a failure") {
    const wrench::test::scratch area;
    const std::filesystem::path file = area.put("empty.yaml", "");

    CHECK(through(wrench::local_file_reader(), file).empty());
}

// COVERS: FR-2.8 | negative
TEST_CASE("a file that is not there is a read failure naming the cause") {
    const wrench::test::scratch area;
    const auto bytes = wrench::local_file_reader().read(area.at("absent.yaml"));

    REQUIRE_FALSE(bytes.has_value());
    CHECK(bytes.error().step == wrench::step::read);
    CHECK(bytes.error().cause == std::errc::no_such_file_or_directory);
    CHECK(bytes.error().message.starts_with("reading "));
    CHECK(bytes.error().message.find("absent.yaml") != std::string::npos);
}

// A directory opens and then fails on the first read, which the standard
// library reports by throwing out of the stream buffer. The seam answers with a
// failure either way, which is what keeps one catch enough for a caller.

// COVERS: FR-2.8 | negative
TEST_CASE("a directory is a read failure and not an escaping exception") {
    const wrench::test::scratch area;
    const auto bytes = wrench::local_file_reader().read(area.path());

    REQUIRE_FALSE(bytes.has_value());
    CHECK(bytes.error().step == wrench::step::read);
    CHECK(bytes.error().cause.value() != 0);
}

// COVERS: FR-6.3 | positive
TEST_CASE("a write lands and reads back byte for byte") {
    const wrench::test::scratch area;
    const std::filesystem::path file = area.at("written.yaml");

    const auto landed = wrench::local_file_writer().write(file, "one: 1\n");

    REQUIRE(landed.has_value());
    CHECK(wrench::test::slurp(file) == "one: 1\n");
}

// COVERS: FR-6.3 | property
TEST_CASE("a written file is readable by anybody who reads what wrench wrote") {
    const wrench::test::scratch area;
    const std::filesystem::path file = area.at("mode.yaml");

    const auto landed = wrench::local_file_writer().write(file, "one: 1\n");

    REQUIRE(landed.has_value());
    // mkstemp creates the temporary at 0600 and a rename keeps that mode, so
    // without a chmod this file would be private where the same file written by
    // the Go, Python or Rust pack is not. A consumer reads what wrench wrote,
    // whichever pack wrote it.
    const auto permissions = std::filesystem::status(file).permissions();
    CHECK((permissions & std::filesystem::perms::owner_read) !=
          std::filesystem::perms::none);
    CHECK((permissions & std::filesystem::perms::owner_write) !=
          std::filesystem::perms::none);
    CHECK((permissions & std::filesystem::perms::group_read) !=
          std::filesystem::perms::none);
    CHECK((permissions & std::filesystem::perms::others_read) !=
          std::filesystem::perms::none);
    CHECK((permissions & std::filesystem::perms::group_write) ==
          std::filesystem::perms::none);
    CHECK((permissions & std::filesystem::perms::others_write) ==
          std::filesystem::perms::none);
}

// COVERS: FR-6.3 | edge
TEST_CASE("an empty write leaves an empty file and not an absent one") {
    const wrench::test::scratch area;
    const std::filesystem::path file = area.at("empty.yaml");

    const auto landed = wrench::local_file_writer().write(file, "");

    REQUIRE(landed.has_value());
    CHECK(std::filesystem::exists(file));
    CHECK(wrench::test::slurp(file).empty());
}

// COVERS: FR-6.3 | positive
TEST_CASE("a write that lands leaves no temporary beside the target") {
    const wrench::test::scratch area;
    const std::filesystem::path file = area.at("written.yaml");

    const auto landed = wrench::local_file_writer().write(file, "one: 1\n");

    REQUIRE(landed.has_value());
    CHECK(wrench::test::entries(area.path()) == 1);
}

// COVERS: FR-6.3 | positive
TEST_CASE("a second write replaces the contents and adds no file") {
    const wrench::test::scratch area;
    const std::filesystem::path file = area.put("written.yaml", "old: 1\n");
    const wrench::local_file_writer shipped;

    REQUIRE(shipped.write(file, "new: 2\n").has_value());

    CHECK(wrench::test::slurp(file) == "new: 2\n");
    CHECK(wrench::test::entries(area.path()) == 1);
}

// The rename is what a reader sees, so a write that cannot rename must leave
// the target as it was. A directory in the target's place is the case a test can
// construct: everything up to the rename succeeds and the rename is refused.

// COVERS: FR-6.3 | negative
TEST_CASE("a write that cannot land leaves the previous contents and no temporary") {
    const wrench::test::scratch area;
    const std::filesystem::path occupied = area.at("occupied.yaml");
    std::filesystem::create_directory(occupied);
    const std::filesystem::path inside =
        area.put("occupied.yaml/inside", "untouched\n");

    const auto landed = wrench::local_file_writer().write(occupied, "one: 1\n");

    REQUIRE_FALSE(landed.has_value());
    CHECK(landed.error().step == wrench::step::write);
    CHECK(landed.error().message.starts_with("writing "));
    CHECK(std::filesystem::is_directory(occupied));
    CHECK(wrench::test::slurp(inside) == "untouched\n");
    // The target and nothing else: the temporary was removed on the way out.
    CHECK(wrench::test::entries(area.path()) == 1);
}

// COVERS: FR-6.3 | negative
TEST_CASE("a write into a directory that is not there is a write failure") {
    const wrench::test::scratch area;
    const auto landed =
        wrench::local_file_writer().write(area.at("absent/file.yaml"), "x\n");

    REQUIRE_FALSE(landed.has_value());
    CHECK(landed.error().step == wrench::step::write);
    CHECK(landed.error().cause == std::errc::no_such_file_or_directory);
}

// COVERS: FR-2.5 | positive
TEST_CASE("the shipped pair is reached through the seams and not by its own type") {
    const wrench::test::scratch area;
    const std::filesystem::path file = area.at("through.yaml");
    const wrench::local_file_writer shipped_out;
    const wrench::writer& out = shipped_out;

    REQUIRE(out.write(file, "one: 1\n").has_value());

    const wrench::local_file_reader shipped;
    const wrench::reader& in = shipped;
    CHECK(through(in, file) == "one: 1\n");
}

// COVERS: FR-2.5a | positive
TEST_CASE("a substituted reader is handed the path and opens no file") {
    const canned_reader substitute("one: 1\n");
    const wrench::reader& seam = substitute;
    const std::filesystem::path nowhere = "/nowhere-that-exists/file.yaml";

    CHECK(through(seam, nowhere) == "one: 1\n");
    CHECK(substitute.asked() == nowhere);
    CHECK_FALSE(std::filesystem::exists(nowhere));
}

// COVERS: FR-2.5a | positive
TEST_CASE("a substituted writer is handed the path and writes no file") {
    const recording_writer substitute;
    const wrench::writer& seam = substitute;
    const std::filesystem::path nowhere = "/nowhere-that-exists/file.yaml";

    REQUIRE(seam.write(nowhere, "one: 1\n").has_value());

    CHECK(substitute.asked() == nowhere);
    CHECK(substitute.kept() == "one: 1\n");
    CHECK_FALSE(std::filesystem::exists(nowhere));
}

// An allocation failure leaves as std::bad_alloc, and the sweep is what takes
// the throwing edge of every allocating call in the two seams. The temporary is
// removed on that path too, which is what the entry count here asserts.
//
// Nothing inside a swept body asserts. An assertion allocates, and the body runs
// with an allocation armed to fail.

// COVERS: FR-6.3 | edge
TEST_CASE("a write that cannot allocate leaves nothing behind") {
    const wrench::test::scratch area;
    const std::filesystem::path file = area.at("written.yaml");
    const wrench::local_file_writer shipped;

    const wrench::test::sweep found = wrench::test::fail_each_allocation(
        [&shipped, &file] { const auto answer = shipped.write(file, "one: 1\n"); });

    CHECK(found.completed);
    CHECK(found.thrown > 0);
    CHECK(wrench::test::entries(area.path()) == 1);
}

// COVERS: FR-2.8 | edge
TEST_CASE("a read that cannot allocate throws rather than answering") {
    const wrench::test::scratch area;
    const std::filesystem::path file = area.put("carried.yaml", "one: 1\n");
    const wrench::local_file_reader shipped;

    const wrench::test::sweep found = wrench::test::fail_each_allocation(
        [&shipped, &file] { const auto answer = shipped.read(file); });

    CHECK(found.completed);
    CHECK(found.thrown > 0);
}

// COVERS: FR-2.8 | edge
TEST_CASE("a read failure that cannot allocate its message throws") {
    const wrench::test::scratch area;
    const std::filesystem::path absent = area.at("absent.yaml");
    const wrench::local_file_reader shipped;

    const wrench::test::sweep found = wrench::test::fail_each_allocation(
        [&shipped, &absent] { const auto answer = shipped.read(absent); });

    CHECK(found.completed);
    CHECK(found.thrown > 0);
}
