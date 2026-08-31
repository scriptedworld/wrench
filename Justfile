# wrench: the delegation layer.
#
# THIS FILE IS BESPOKE AND NO TEMPLATE WRITES IT. Settled by our user,
# silo c564005: a project that holds several packs gets a delegating Justfile
# that calls the constituent packs' Justfiles. What it delegates to differs per
# repository, which is exactly the kind of thing a template should not guess.
#
# So it does NOT import just/base.just, and it defines the ten itself. Each pack
# is an ordinary single-language project with its own Justfile from the
# templates, and nothing about them knows they are inside wrench.
#
# THE TWO-WORD INTERFACE HOLDS ALL THE WAY UP. `just checks` here means every
# pack's checks, so a person moving between wrench and any other tree types the
# same words and never learns wrench is different. That is the property worth
# having and it is why this file carries all ten names rather than only the ones
# that delegate.
#
# ================== TWO MEASURED FACTS THIS FILE RESTS ON ==================
#
# 1. `just -f go/Justfile test` ALREADY RUNS WITH THE WORKING DIRECTORY SET TO
#    THAT JUSTFILE'S DIRECTORY. No `cd`, no `--working-directory`. All four
#    forms tested behaved identically, so a delegating recipe is one line and
#    relative paths inside the called recipe resolve against its own pack.
#
# 2. THE NAIVE LOOP EXITS 0 WHEN A PACK FAILS. A plain
#    `@for p in ...; do just -f $p/Justfile test; done` continues past the
#    failure and the root reports success, which is the estate's signature
#    hazard arriving in the delegation pattern. Measured: python failed, the
#    loop carried on, root exit=0.
#
#    Every recipe below is therefore a shebang recipe with `set -euo pipefail`.
#    Verified: exit 1 on a failing pack, exit 0 when all pass, and it stops at
#    the pack that failed rather than running the rest.
#
#    DO NOT REWRITE THESE AS `@for` ONE-LINERS. That is the defect.
# ===========================================================================

PACKS := "go python rust"

default:
    @just --list

# _each runs one recipe name across every pack that has a Justfile, stopping at
# the first pack that HAS one and fails.
#
# AN ABSENT PACK IS AN ABSENCE, NOT A FAILURE, and conflating the two made the
# order of PACKS decide whether any work happened at all. Measured by wrench: go
# sorts first, wrench has no go/Justfile, so `just test` stopped there and ran
# ZERO suites while reporting a correct exit 1. It reported honestly and did
# nothing.
#
# Reordering to put an adopted pack first fixes the symptom and has to be undone
# later, so this skips what is absent instead. Order now decides nothing.
#
# AND RUNNING NOTHING IS ITS OWN FAILURE. If no pack has a Justfile this exits 1
# saying so, rather than succeeding over an empty loop. A gate that ran nothing
# must not report green: scanning nothing and finding nothing are one green.
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

# THE PARITY CHECK IS WRENCH'S ALONE and belongs at the root because it is the
# only thing that reads all three packs at once. `bin/test-suite-parity.py`
# fails when one pack's suite covers something another's does not, which is what
# "in parallel and in sync" is enforced by rather than hoped for.
#
# It is separate from `_each checks` because no pack can run it: a pack that
# could would have to know about its siblings, which is what this layer exists
# to prevent.
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

# A CLEAN RECIPE MUST NOT REMOVE ANYTHING ANOTHER PROCESS EXECUTES, and at this
# level that includes not reaching into the packs by hand. Each pack's own clean
# knows what it may remove; this one adds only what belongs to the root.
#
# schemas/ and testdata/ are NEVER removed. They are shared by every pack and
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
