# The Python half for wrench/python.
#
# This is an ordinary single-language project that happens to sit in a
# subdirectory. wrench is several projects and one delegator (silo c564005), so
# `wrench/python` takes the templates like any other python tree and only
# `wrench/Justfile` is bespoke.
#
# The jigs are at the repository root. `wrench/` carries
# bolt.common-quality.yaml, bolt.python-std-quality.yaml and bolt.secrets.yaml;
# `wrench/python/` carries none. bolt reaches them with --config-dir:
#
#     bolt common-quality . --config-dir ..
#
# wrench's root jig makes the same call from the other direction:
# `bolt --config-dir {config_dir} --definitions wrench common-quality python`.
# Run from the subdirectory, the result lands in the subdirectory and the
# verdict reads correctly.
#
# `_verdict` in just/base.just is variadic, so the calls below pass
# `--config-dir ..` and this file needs no copy of it.
#
# This file does not run the go or rust packs, and it does not run wrench's own
# `bolt.wrench-quality.yaml`, which gates all three together and holds the
# suites level with a parity checker. Both belong to the root delegator.
#
# LICENSE and NOTICE here are symlinks to the repository root, because PEP 639
# resolves `license-files` globs inside the project directory and `../LICENSE`
# is not permitted. Nothing below touches them; they are noted because a clean
# recipe written from a listing would see two files and not two links.

# everything: quality, tests, coverage, secrets
checks:
    @just _verdict python-std-quality --config-dir ..

# the secrets jig alone, from one level up
leak-scan:
    @just _verdict secrets --config-dir ..

# The suite runs from the repository root so the pack finds `schemas/`, which is
# two levels above this package and is the one copy every pack reads. wrench's
# own jig describes its python-test task the same way.

# the suite
test:
    cd .. && PYTHONPATH=python python3 -m pytest python/tests -q

# Coverage is measured and not enforced, per the jig's own footer: the per-file
# threshold waits on an adapter that reads Cobertura XML, and an aggregate is
# refused for the reason hard rule 5 gives.

# the suite with coverage, and the minimum enforced
coverage:
    #!/usr/bin/env bash
    set -euo pipefail
    cd ..
    PYTHONPATH=python coverage run -m pytest python/tests -q
    coverage report
    coverage xml -o python/coverage.xml
    echo "coverage: measured, NOT enforced. No per-file threshold exists yet."

# formatting verified, nothing written
format-check:
    ruff format --check .
    ruff check .

# formatting written
format:
    ruff format .
    ruff check --fix .

# may be a no-op
build:
    @echo "build: python needs no build step; see dist"

# whatever this language distributes
dist:
    python3 -m build

# Install this editable. The schemas are read from `schemas/` at the repository
# root, two levels above this package, so a copied install leaves the pack
# looking for files that are not beside it. That is FR-3.2, and this project's
# pyproject says so at the bottom.

# put the built artefact where it is used from
install:
    pip install -e .

# build/ and *.egg-info are removed here because leaving them turns this
# repository's gate red. setuptools copies the package into
# `build/lib/wrench/`, mypy then finds two modules named `wrench` and reports
# `Duplicate module named "wrench" (also at "./build/lib/wrench/__init__.py")`,
# which stops it before it checks anything. pylint reads the copy too and
# reports every file as duplicate-code against itself.
#
# With both present the gate is `success: false` on `types exited 2` and
# `analyse exited 8`; removing them alone returns it to `success: true` over
# 28 executions with nothing else changed.
#
# Neither is an installed artefact and nothing executes either, so the rule
# above about leaving deployed files alone does not reach them. `just install`
# is editable, which writes no copy.

# remove run directories and build output
clean:
    rm -rf .bolt-* build dist coverage.xml .coverage
    rm -rf *.egg-info .ruff_cache .mypy_cache .pytest_cache .complexipy_cache
    find . -name __pycache__ -type d -prune -exec rm -rf {} +
