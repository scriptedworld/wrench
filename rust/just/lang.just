# The Rust half for wrench/rust.
#
# ================== THIS IS NOT templates/rust-library ======================
#
# `templates/rust-library` is a Copier template. Rendering it into this pack
# would scaffold `Cargo.toml`, `src/lib.rs`, `tests/` and `deny.toml` OVER real
# code. wrench was right not to run it.
#
# **A lang.just for an existing pack is a different artefact from a template
# that creates one**, and nothing in the factory produced the first until now.
# That gap is why `rust/` had no Justfile, and it is half of why the root
# delegator ran zero suites: go sorts first and is also absent, which masked it.
#
# What differs from what the template would have written, all measured against
# this pack rather than assumed:
#
#   no deny.toml here, so no `cargo deny check`. The template ships one; this
#   pack has none and inventing a licence policy for somebody else's crate is
#   not a Justfile's business. Add the task when the pack adds the file.
#
#   `build.rs` regenerates the schema embedding from `../schemas` on every
#   build, so `clean` running `cargo clean` costs a regeneration rather than
#   losing anything. Harmless, and worth knowing before wondering why a clean
#   build is slower here.
#
#   `tests/compile-fail/` is trybuild, which runs the compiler on files that
#   are MEANT to fail and compares stderr against a checked-in expectation.
#   `cargo test` runs it like any other test. It is named here because a
#   failure there reads as a compiler error rather than a test failure.
#
# THE JIGS ARE AT THE REPOSITORY ROOT, as they are for the python pack, so
# every bolt call carries `--config-dir ..`. base's `_verdict` is variadic and
# takes it.
#
# THE ROOT JIG ALSO RUNS THIS PACK, as `cargo test --manifest-path
# rust/Cargo.toml`. That is not duplication to remove: the root jig gates all
# three packs together and holds their suites level, and this file is what a
# person runs while working in `rust/`.
# ===========================================================================

# everything: quality, tests, coverage, secrets
checks:
    @just format-check
    @just _cargo-lint
    @just test
    @just doc
    @just _verdict common-quality --config-dir .. --definitions wrench

# clippy with warnings denied, so a lint declared in Cargo.toml is enforced
_cargo-lint:
    cargo clippy --all-targets -- -D warnings

# the suite, including the trybuild compile-fail cases and the doc examples
test:
    cargo test

# A LIBRARY IS ITS DOCUMENTATION, so a broken intra-doc link is a defect rather
# than a blemish: it is a piece of the contract pointing at nothing.

# the documentation, with a broken intra-doc link failing the build
doc:
    RUSTDOCFLAGS="-D warnings" cargo doc --no-deps

# COVERAGE IS JUDGED PER FILE, which is hard rule 5. There is no entry point to
# reach by running a binary, because this pack is a library with no main.rs, so
# every line is reachable from an ordinary test.
#
# DO NOT SET THE THRESHOLD TO 100. At exactly 100 the check exits 1 with a
# report showing every file at 100.00% and prints nothing on stderr, so a pack
# that met the bar fails silently and reads as broken tooling.
#
# 80 IS A PLACEHOLDER. The estate declares no Rust coverage minimum anywhere,
# and this pack's real floor is wrench's to set.

# the suite with coverage, and the minimum enforced per file
coverage:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v cargo-llvm-cov >/dev/null 2>&1; then
        echo "coverage: cargo-llvm-cov is not installed, so nothing was measured" >&2
        echo "  cargo install cargo-llvm-cov" >&2
        exit 1
    fi
    cargo llvm-cov clean --workspace
    cargo llvm-cov --no-report
    cargo llvm-cov report --fail-under-file-lines 80

# formatting verified, nothing written
format-check:
    cargo fmt --check

# formatting written
format:
    cargo fmt

# every target, so the tests compile too
build:
    cargo build --all-targets

# the .crate a registry would serve. `cargo package` also VERIFIES by building
# what it packed, which catches a crate that only compiles because of a file
# the package would not carry. That matters here: build.rs reads ../schemas,
# which is OUTSIDE this pack, so packaging is the check that says whether this
# crate is self-contained.

# whatever this language distributes
dist:
    cargo package

# put the built artefact where it is used from
install:
    @echo "install: nothing to install; a dependent adds wrench to its Cargo.toml"

# `cargo clean` removes target/ and nothing here is on PATH or executed by
# anything else, so there is no artefact to preserve. build.rs regenerates the
# schema embedding on the next build.

# remove run directories and build output
clean:
    rm -rf .bolt-*
    cargo clean

# the secrets jig alone, from one level up
leak-scan:
    @just _verdict secrets --config-dir ..
