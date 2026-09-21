#include "support.hpp"

#include <cstddef>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <ranges>
#include <stdexcept>
#include <string>
#include <string_view>
#include <system_error>

namespace wrench::test {

scratch::scratch() {
    std::string pattern =
        (std::filesystem::temp_directory_path() / "wrench-test-XXXXXX").string();
    if (::mkdtemp(pattern.data()) == nullptr) {
        throw std::runtime_error("mkdtemp failed for " + pattern);
    }
    path_ = pattern;
}

scratch::~scratch() {
    std::error_code ignored;
    std::filesystem::remove_all(path_, ignored);
}

const std::filesystem::path& scratch::path() const { return path_; }

std::filesystem::path scratch::at(std::string_view relative) const {
    return path_ / relative;
}

std::filesystem::path scratch::put(const std::filesystem::path& relative,
                                   std::string_view body) const {
    const std::filesystem::path full = path_ / relative;
    std::filesystem::create_directories(full.parent_path());
    std::ofstream stream(full, std::ios::binary | std::ios::trunc);
    stream.write(body.data(), static_cast<std::streamsize>(body.size()));
    return full;
}

std::string slurp(const std::filesystem::path& path) {
    std::ifstream stream(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()};
}

std::size_t entries(const std::filesystem::path& directory) {
    return static_cast<std::size_t>(
        std::ranges::distance(std::filesystem::directory_iterator(directory)));
}

}  // namespace wrench::test
