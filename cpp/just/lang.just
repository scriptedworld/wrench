# The C++ half for wrench/cpp.
#
# The jig reads two artefacts this pack has to produce first: the compilation
# database, which is the only statement of what is compiled and how, and the
# gcov profile the suite leaves behind. `cpp-profile` makes both, and every
# recipe that needs either goes through it.
#
# The jigs are at the repository root, as they are for the Python and Rust
# packs, so every bolt call carries `--config-dir ..`. base's `_verdict` is
# variadic and takes it.
#
# `common-quality` is not run here, and that is measured rather than an
# oversight. Its traceability and suppression checkers read Go, Python, Ruby,
# Rust and shell, and neither reads `.cpp` or `.hpp`, so a run at this base sees
# no tests at all and fails every requirement. The root jig runs common-quality
# over the whole repository, where it passes on the files it can read.
# `clank/inbox/toolbox/common-quality-does-not-read-cpp` holds the gap.

# The build directory is emptied first, every time. gcov leaves a notes file per
# object at compile time and a counts file per object at run time, and either one
# surviving a configuration change is read as this run's. infobot measured the
# case: after its test sources stopped being instrumented, their notes files
# outlived the change and the jig failed both files at 0% of lines.

# everything: the profile the jig reads, then the jig
checks:
    @just cpp-profile
    @just _verdict cpp-std-quality --config-dir .. --definitions cpp-std-quality

# the suite, instrumented, leaving the database and the profile the jig reads
cpp-profile:
    rm -rf build
    cmake -S . -B build -G Ninja -DWRENCH_COVERAGE=ON -DCMAKE_BUILD_TYPE=Debug
    cmake --build build
    ln -sfn build/compile_commands.json compile_commands.json
    ./build/wrench-tests

# The suite alone, uninstrumented, which is what a person runs while working.
# It writes the same database, so the analysis tasks can be run against a tree
# that has never been measured for coverage.
#
# WRENCH_COVERAGE is named here with OFF rather than left out. CMake caches an
# option, so after `cpp-profile` a configure that does not mention it keeps the
# instrumented build and leaves counts files behind that the next profile run
# would read as its own.

# The gcov artefacts go with it. An uninstrumented build cannot write one, so
# any left in the build tree are an earlier profile's and would be read as this
# tree's by a gcovr run that did not go through `cpp-profile`. The two names are
# the only files removed and only inside the build directory.

# the suite
test:
    cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug -DWRENCH_COVERAGE=OFF
    find build \( -name '*.gcda' -o -name '*.gcno' \) -delete
    cmake --build build
    ln -sfn build/compile_commands.json compile_commands.json
    ./build/wrench-tests

# Coverage is judged per file, which is hard rule 5, and gcovr's own thresholds
# are aggregate: they let a well-tested file carry an untested one. The per-file
# judgement is the jig's `tests` task, through toolbox's lcov adapter, so this
# recipe produces the profile and shows it and `just checks` is what enforces
# the minimum.

# the suite with coverage, reported per file
coverage:
    @just cpp-profile
    gcovr --root . --exclude '(^|/)(\.ephemera|bin|adapters|build|tests)/' --txt

# formatting verified, nothing written
format-check:
    #!/usr/bin/env bash
    set -euo pipefail
    clang-format --style=file:../config/cpp/clang-format.yaml --dry-run --Werror \
        include/wrench/*.hpp src/*.cpp tests/*.hpp tests/*.cpp

# formatting written
format:
    #!/usr/bin/env bash
    set -euo pipefail
    clang-format --style=file:../config/cpp/clang-format.yaml -i \
        include/wrench/*.hpp src/*.cpp tests/*.hpp tests/*.cpp

# the library and the suite, built and not run
build:
    cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug -DWRENCH_COVERAGE=OFF
    cmake --build build

# A C++ library is distributed as sources plus a CMake package a consumer finds,
# which is task 50's work and not written yet.

# nothing is distributed yet
dist:
    @echo "dist: a consumer takes this pack by path until the package is exported"

# nothing is installed
install:
    @echo "install: nothing to install; a dependent adds this pack to its CMake build"

# Everything here is build output that a build recreates. Nothing in `build/` is
# executed by anything outside this pack, and the database is a symlink into it
# that a stale run would leave pointing at nothing.

# remove run directories and build output
clean:
    rm -rf .bolt-* build compile_commands.json

# the secrets jig alone, from one level up
leak-scan:
    @just _verdict secrets --config-dir ..
