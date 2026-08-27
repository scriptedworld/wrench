# A repro script that fails silently prints the number you wanted

## What happened

2026-08-27. I filed a finding about language startup cost with a `repro.sh` that
regenerated its own figures. The script wrote its two compiled sources as `_p.go`
and `_p.rs`.

**The go tool ignores any file whose name begins with `_` or `.`**, so the build
never had a source to build:

    go build -o _pgo _p.go
    package command-line-arguments: no Go files in <dir>

The sources were built in a `&&` chain, so `rustc` never ran either. Neither
binary existed. The timing loop then invoked both under `|| true`, measured
nothing, and reported **0ms for Go and 0ms for Rust**.

silo caught it while resolving the entry, and re-measured by hand before writing
the decision down.

## Why 0ms is the dangerous value

The script was written to support the claim that compiled languages start faster
than interpreted ones. `0ms` does not read as *this did not run*. It reads as
*even faster than claimed*.

**A wrong number that contradicts the conclusion gets investigated. A wrong
number that agrees with it gets published.** The failure mode is not that the
script broke; it is that it broke in the direction nobody checks.

The real figures, re-measured over 20 runs of do-nothing programs, were rust 2ms,
go 3ms, python3 23ms, node 25ms. The conclusion survived. It survived because
somebody re-derived it, not because the evidence held.

## The same shape in two more of my scripts

Found while looking for other copies, and both are mine:

    PYTHONPATH=python /usr/bin/python3 -c "import wrench" 2>&1 | tail -2 \
        || echo "(failed, as FR-6.2a records)"

**That fallback is dead code.** A shell takes a pipeline's status from its last
command, so the guard reads `tail`'s status and never the probe's:

    false | tail -2 || echo FALLBACK     prints nothing, exits 0

Measured against the real probe: the import exits **1** run directly and **0**
through the pipe. The evidence in that finding is correct only because the
traceback prints itself. Had the import started succeeding, the section would
have gone quiet and no fallback would have fired, and silence reads as nothing to
report rather than as an expectation violated.

`set -eu` does not cover this. It does not apply inside a pipeline.

## What to do instead

**Assert that the artifact exists before measuring it.** A missing binary should
end the script, not produce a datum.

    go build -o pgo p.go
    test -x ./pgo || { echo "build failed, refusing to time nothing" >&2; exit 1; }

**Name sources so the toolchain will read them.** No leading `_` or `.` for Go.

**Take the status from the command, not from the pipeline.** Either drop the pipe
while checking, or set `pipefail` where the shell has it:

    if ! PYTHONPATH=python /usr/bin/python3 -c "import wrench" 2>err.txt; then
        echo "failed as expected"; tail -2 err.txt
    else
        echo "UNEXPECTED: the import succeeded"; exit 1
    fi

**Write the unexpected branch loudly.** Every probe of an expected failure needs
a branch that shouts when the expectation is violated. A probe with only the
expected path cannot tell you the world changed.

## The rule this is a case of

Hard rule 6 says verify with the tool rather than the exit status, and
`read-the-artifact-not-the-summary-line.md` in this directory is the same rule
about a check.

**This one is a layer down, in the evidence rather than in the check.** A gate
caught the earlier case because a gate cannot decide the number looked fine. No
gate runs a `repro.sh`, so nothing catches this except writing the script to fail
loudly in the first place, and a reader who re-measures instead of trusting the
artifact.

That is why a finding carries the command and not only the figure. silo re-ran
the measurement rather than reading my output, which is the only reason the wrong
number cost nothing.
