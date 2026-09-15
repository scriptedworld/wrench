# wrench: the delegation layer.
#
# No template writes this file. A project that holds several packs gets a
# delegating Justfile that calls each pack's own Justfile (silo c564005), and
# what it delegates to differs per repository, so a template should not guess.
#
# It does not import just/base.just and defines the ten recipes itself. Each
# pack is an ordinary single-language project with its own Justfile from the
# templates, and nothing in them knows they sit inside wrench.
#
# The two-word interface holds all the way up. `just checks` here means every
# pack's checks, so somebody moving between wrench and any other tree types the
# same words. That is why this file carries all ten names, including the ones
# that do not delegate.
#
# Two things about just that this file depends on:
#
# 1. `just -f go/Justfile test` already runs with the working directory set to
#    that Justfile's directory, with no `cd` or `--working-directory`. All four
#    forms tested behaved identically, so a delegating recipe is one line and
#    relative paths inside the called recipe resolve against its own pack.
#
# 2. A plain `@for p in ...; do just -f $p/Justfile test; done` exits 0 when a
#    pack fails: python failed, the loop carried on, and the root exited 0.
#    Every recipe below is a shebang recipe with `set -euo pipefail` instead,
#    which exits 1 on a failing pack, exits 0 when all pass, and stops at the
#    pack that failed.
#
#    Do not rewrite these as `@for` one-liners.

PACKS := "go python rust"

default:
    @just --list

# _each runs one recipe name across every pack that has a Justfile, stopping at
# the first pack that has one and fails.
#
# A pack with no Justfile is skipped, not failed. Treating it as a failure lets
# the order of PACKS decide whether any work happens: go sorts first, and with
# no go/Justfile `just test` stopped there, ran no suites at all, and exited 1.
# Reordering PACKS would only hide that, so the order decides nothing.
#
# Running nothing is a failure of its own. If no pack has a Justfile this exits
# 1 and says so, because a gate that ran nothing must not report green.
_each recipe:
    #!/usr/bin/env bash
    set -euo pipefail
    ran=0
    skipped=()
    for p in {{ PACKS }}; do
        if [ ! -f "$p/Justfile" ]; then
            skipped+=("$p")
            continue
        fi
        printf '\n### %s: %s\n' "$p" "{{ recipe }}"
        if ! just -f "$p/Justfile" "{{ recipe }}"; then
            printf '\n%s failed in the %s pack\n' "{{ recipe }}" "$p" >&2
            exit 1
        fi
        ran=$((ran + 1))
    done
    if [ ${#skipped[@]} -gt 0 ]; then
        printf '\nnot adopted, skipped: %s\n' "${skipped[*]}"
    fi
    if [ "$ran" -eq 0 ]; then
        printf 'no pack has a Justfile, so %s ran nothing\n' "{{ recipe }}" >&2
        exit 1
    fi

# everything, in every pack
checks:
    @just _each checks
    @just _parity

# The parity check belongs to wrench alone and sits at the root because it is
# the only thing that reads all three packs at once. `bin/test-suite-parity.py`
# fails when one pack's suite covers something another's does not, which is how
# "in parallel and in sync" gets enforced.
#
# It is separate from `_each checks` because no pack can run it without knowing
# about its siblings, and the packs are kept from knowing.
_parity:
    ./bin/test-suite-parity.py --requirements docs/REQUIREMENTS \
        --suite go='go/*_test.go' \
        --suite python='python/tests/*.py' \
        --suite rust='rust/tests/*.rs' .

# the suite, in every pack
test:
    @just _each test

# the suite with coverage, in every pack
coverage:
    @just _each coverage

# formatting verified, nothing written
format-check:
    @just _each format-check

# formatting written
format:
    @just _each format

# may be a no-op
build:
    @just _each build

# whatever this language distributes
dist:
    @just _each dist

# put the built artefact where it is used from
install:
    @just _each install

# A clean recipe must not remove anything another process executes, and at this
# level that means not reaching into the packs by hand. Each pack's own clean
# knows what it may remove; this one adds only what belongs to the root.
#
# schemas/ and testdata/ are never removed. They are shared by every pack and
# belong to none, and rust/build.rs regenerates its embedding from schemas/ on
# every build.

# remove run directories and build output
clean:
    @just _each clean
    rm -rf .bolt-*

# the secrets jig alone, over the whole repository rather than per pack
leak-scan:
    @just _verdict secrets

# Reads the verdict out of result.yaml and never bolt's exit status, which is 0
# whenever a run was carried out at all. The same recipe as just/base.just's,
# copied because this file does not import it.
_verdict jig:
    #!/usr/bin/env bash
    set -euo pipefail
    out=$(bolt "{{ jig }}" .)
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
