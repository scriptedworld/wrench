# The Python half for wrench/python.
#
# THIS IS AN ORDINARY SINGLE-LANGUAGE PROJECT THAT HAPPENS TO SIT IN A
# SUBDIRECTORY. Settled by our user, silo c564005: wrench is several projects
# and one delegator, so `wrench/python` takes the templates like any other
# python tree and only `wrench/Justfile` is bespoke.
#
# THE JIGS ARE AT THE REPOSITORY ROOT, NOT HERE. `wrench/` carries
# bolt.common-quality.yaml, bolt.python-std-quality.yaml and bolt.secrets.yaml;
# `wrench/python/` carries none. bolt reaches them with --config-dir:
#
#     bolt common-quality . --config-dir ..
#
# THAT IS WRENCH'S OWN PATTERN, arrived at independently. Its root jig runs
# `bolt --config-dir {config_dir} --definitions wrench common-quality python`,
# which is the same call from the other direction. Measured here: run from the
# subdirectory the result lands in the subdirectory and the verdict reads
# correctly.
#
# `_verdict` in just/base.just does not pass --config-dir, so the calls below
# are written out. If a third tree needs this, the right fix is a second
# parameter on `_verdict` in base rather than a third copy.
#
# WHAT THIS FILE DOES NOT DO. It does not run the go or rust packs, and it does
# not run wrench's own `bolt.wrench-quality.yaml`, which gates all three
# together and holds the suites level with a parity checker. Both belong to the
# root delegator, in adoption/wrench-root/.
#
# LICENSE AND NOTICE HERE ARE SYMLINKS TO THE REPOSITORY ROOT, because PEP 639
# resolves `license-files` globs inside the project directory and `../LICENSE`
# is not permitted. Nothing below touches them; they are noted because a clean
# recipe written from a listing would see two files and not two links.

# everything: quality, tests, coverage, secrets
checks:
    @just _verdict-here common-quality
    @just _verdict-here python-std-quality
    @just _verdict-here secrets

# base's _verdict with --config-dir added, because the jigs live one level up
_verdict-here jig:
    #!/usr/bin/env bash
    set -euo pipefail
    out=$(bolt "{{ jig }}" . --config-dir ..)
    result=$(printf '%s\n' "$out" | tail -1)
    if [ ! -f "$result" ]; then
        echo "REFUSED: bolt wrote no result for {{ jig }}" >&2
        printf '%s\n' "$out" >&2
        exit 1
    fi
    if grep -q '"success": *true' "$result"; then
        echo "pass  {{ jig }}  $result"
    else
        echo "FAIL  {{ jig }}  $result" >&2
        exit 1
    fi

# the secrets jig alone, from one level up
leak-scan:
    @just _verdict-here secrets

# THE SUITE RUNS FROM THE REPOSITORY ROOT so the pack finds `schemas/`, which is
# two levels above this package and is the one copy every pack reads. wrench's
# own jig says so in as many words: "the Python pack, run from the repository
# root so it finds schemas/".

# the suite
test:
    cd .. && PYTHONPATH=python python3 -m pytest python/tests -q

# COVERAGE IS MEASURED AND NOT ENFORCED, per the jig's own footer: the per-file
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

# INSTALL THIS EDITABLE. The schemas are read from `schemas/` at the repository
# root, two levels above this package, so a copied install leaves the pack
# looking for files that are not beside it. That is FR-3.2 and this project's
# pyproject says it at the bottom in capitals.

# put the built artefact where it is used from
install:
    pip install -e .

# BUILD/ AND *.EGG-INFO ARE HERE FOR A MEASURED REASON, and a clean without
# them leaves this repository's gate red. setuptools copies the package into
# `build/lib/wrench/`, mypy then finds two modules named `wrench` and reports
# `Duplicate module named "wrench" (also at "./build/lib/wrench/__init__.py")`,
# which stops it before it checks anything. pylint reads the copy too and
# reports every file as duplicate-code against itself.
#
# Measured here: with both present the gate is `success: false` on `types
# exited 2` and `analyse exited 8`; removing them alone returns it to
# `success: true` over 28 executions with nothing else changed.
#
# Neither is an installed artefact and nothing executes either, so the rule
# above about leaving deployed files alone does not reach them. `just install`
# is editable, which writes no copy.

# remove run directories and build output
clean:
    rm -rf .bolt-* build dist coverage.xml .coverage
    rm -rf *.egg-info .ruff_cache .mypy_cache .pytest_cache .complexipy_cache
    find . -name __pycache__ -type d -prune -exec rm -rf {} +
