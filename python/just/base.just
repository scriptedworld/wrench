# The ten recipes, supplied for every project whatever it is written in.
#
# A recipe that does not apply exists and succeeds instead of being absent, so
# `just build` never fails for the wrong reason. A language layer overrides
# whichever of these it can really implement, by writing just/lang.just; a
# project overrides further in just/project.just. Both beat this file.
#
# `checks` invokes the others through `just`, which re-enters the import chain,
# so it reaches the language layer's real recipe and not the no-op below. With
# a lang.just defining `test`, `just checks` runs that one.

# Three things every bolt call here does, and why.
#
# 1. It reads the verdict out of result.yaml and never bolt's exit status.
#    bolt exits 0 whenever it carried a run out, whatever the tools concluded.
#    A jig with one passing and one failing task printed "success": false into
#    result.yaml and exited 0. Reading the artifact and not the exit status is
#    a standing rule here.
#
#    bolt's own --result-to-exitcode does make the status carry the verdict,
#    and is still not used: it collapses a refusal, where no result was
#    written at all, into the same exit 1 as a failed run. Those are different
#    answers and a recipe that cannot tell them apart reports the wrong one.
#
# 2. It takes bolt's default output directory and names no --output-dir at
#    all. A fixed directory is what is forbidden, because bolt refuses one that
#    already holds a run, so naming one works exactly once. The default is
#    unique per run and `clean` removes them.
#    Every project answering to the same two words is a settled decision.
#
# 3. It quotes the path it read. A verdict with no artifact beside it cannot be
#    checked by whoever reads the output.

# The recipe is variadic because an adopter that fills a placeholder has to
# pass its own definitions, and a recipe cannot add an argument to another
# recipe's command.
#
#     just _verdict go-std-quality --definitions go-std-quality
#     just _verdict common-quality --definitions skid
#     just _verdict common-quality --config-dir ..        jigs one level up
#
# Without it the failure does not look like a missing flag. The placeholder
# keeps its default and the jig reports a problem in the adopter's own tree:
# qwark's `entrypoint` stayed `true`, so cover-entrypoint.sh never ran and
# main.go read 0.0% against an 80% floor. Skid's `requirements` stayed the
# retired single-file path, so traceability and suppressions both failed. On a
# fixture, the task passes with the flag and the same task fails without it,
# and nothing in either message says "definitions".
#
# So the next adopter would go and change their coverage or requirements
# configuration instead of suspecting this file. qwark and skid both hit it
# independently: two of two adopters, different languages, same cause.
_verdict jig *flags:
    #!/usr/bin/env bash
    set -euo pipefail
    out=$(bolt {{ flags }} "{{ jig }}" .)
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

# Everything. Quality, tests, coverage, secrets and requirements coverage: the
# biggest full gate this tree can run. The other nine exist so a piece can be
# run alone during development; this is what runs before anything lands.
#
# The secrets scan arrives through common-quality, which composes it as a child
# so `bolt.secrets.yaml` stays the one definition of what a scan is. Do not add
# `leak-scan` here: it would run the same jig a second time.

# everything: quality, tests, coverage, secrets
checks:
    @just _verdict common-quality
    @just test
    @just coverage

# the suite
test:
    @echo "test: no language layer applied"

# the suite with coverage, and the minimum enforced
coverage:
    @echo "coverage: no language layer applied"

# formatting verified, nothing written
format-check:
    @echo "format-check: no language layer applied"

# formatting written
format:
    @echo "format: no language layer applied"

# may be a no-op
build:
    @echo "build: nothing to build"

# whatever this language distributes
dist:
    @echo "dist: nothing to distribute"

# put the built artefact where it is used from
install:
    @echo "install: nothing to install"

# A clean recipe must not remove anything another process executes.
#
# That is neither "do not delete bin/" nor "do not delete anything on PATH".
# The rule is about who runs the file, because in this estate a project's build
# output and its deployed artefact are routinely the same file, and the ways a
# file gets reached are not limited to PATH.
#
# The PATH directory itself can be a symlink into a project tree:
#
#     ~/bin -> <some project>/bin
#
# So a clean in that project that removes bin/ takes out the entire PATH
# directory, not one command, and every other project reachable through it goes
# at the same time. Two of the commands behind such a link were a build gate and
# a pre-execution hook. Removing the second changes what every process is
# permitted to do; it does not merely degrade one program.
#
# Being reachable is not the same as being on PATH, and the case that caused
# the outage was not on PATH at all: a link in one project pointing into
# another, invoked by absolute path from a configuration file.
#
# A check that swept PATH would have missed it. So before deleting a path, ask
# whether anything executes it, including hooks, service units and
# configuration, and not merely whether it is on PATH.
#
# This has happened. infobot's clean carried `rm -f bin/statusline bin/forget`
# under the heading "remove build output". Those were deployed artefacts that
# Claude Code executes on every event in every session, and running `just
# clean` took the whole estate's telemetry down for 25 minutes: fifteen status
# files stopped being written at 20:31:11, and every instrument reading them
# kept printing the last values as current.
#
# Why it will happen again without this note, in infobot's own words: the next
# person to write a clean recipe from this template will assume build output is
# disposable, because in most projects it is.
#
# So a language layer overriding this removes run directories, coverage output
# and intermediate build trees, and leaves the installed artefact alone. `just
# install` is what refreshes that, and it already compares bytes, not
# timestamps.

# remove run directories and build output
clean:
    rm -rf .bolt-*

# Named leak-scan and not secrets, because that name trips its own scanner.
#
# detect-secrets reads a recipe name as a key and the following line as its
# value, so `secrets:` with an ordinary body is reported as a Secret Keyword
# and a project fails its own leak check on the recipe that runs it.
#
# Two separate measurements of this both got the wrong answer. Every fixture
# either of them used carried just's `@` quiet marker, because that is how
# recipes are written here, and the `@` happens to break the pairing:
#
#     secrets:  +  just _verdict secrets    FLAGGED
#     secrets:  +  @just _verdict secrets   clean
#
# So both concluded the name was safe from a fixture that was clean by
# accident. The fixture had inherited the habit of the thing it was testing.
#
# The verdict also depends on prose. This file stays clean with the `@`
# removed, while the same three lines cut out of it flag, because the word
# appears eight times in the comments above. The check cleared a file whose
# name was genuinely hazardous, and would equally condemn a file that had done
# nothing but lose a comment: wrong in both directions, from an edit nobody
# would think to check.
#
# `leak-scan` is clean with no `@`, in isolation, and with a body that itself
# invokes `bolt secrets`. The jig keeps its name: `bolt.secrets.yaml` is
# toolbox's and is untouched. Only the recipe moved.
#
# Every project answering to the same two words is a settled decision.

# the secrets jig alone
leak-scan:
    @just _verdict secrets
