# A green gate reports what it looked at, not what is true

Every serious problem found on 2026-09-22 and 2026-09-23 was something a check
could not see, rather than something a check reported. The gate was green
throughout, and the green meant less than it looked like.

## What was invisible, each measured the day it was found

**The Go pack had never been linted.** The root jig ran `gofmt`, `go vet` and
`go test`. Adopting `go-std-quality` at the pack's base reported 193 findings.

That first count was 141, and it was the tool's cap. `golangci-lint` stops
at 50 issues per linter and 3 per issue type unless told otherwise, and the
shared config sets neither. `lll 50` and `paralleltest 50` were the ceiling, not
the count. Run it with `--max-issues-per-linter 0 --max-same-issues 0` before
quoting a number.

Coverage had never been measured. `adapters/python/coverage.py` was not
linked into this repository, so the task that reads it failed with exit 127 and
the failure read as a broken adapter rather than as an unmeasured pack. Two Go
files were under the minimum when it was finally run.

**The suppression register reads no TypeScript and no C++.** Its `SUFFIXES` set
lists Go, Python, Rust, Ruby and three shells. Seven `deno-lint-ignore` pragmas
sat in the TypeScript pack unregistered, and the register reported the
repository clean. Filed as
`clank/inbox/toolbox/the-suppression-register-reads-no-typescript-or-cpp`.

The wording check only ever read `python/`, because `common-quality` ran at
that pack's base. 22 errors were waiting in the first tree it had not read.

`bin/test-suite-parity.py` skipped 3 of 46 requirement rows. Its row pattern
required a bracketed status marker, and FR-2.11, FR-4.8 and FR-4.9 carry none,
so they matched nothing and left the comparison without a word. A Go JSON defect
was sitting behind that gap: the codec wrote `map[int]string` as `{"1": "x"}`
where the YAML codec refused it.

The Rust pack's own `checks` had been failing for months, on contract rows
it cannot discharge at its own base, because nothing ever ran that recipe.

## The shape

In every case the tool ran, exited 0, and answered a narrower question than the
one being asked of it. None of them was a false pass in the sense of a broken
assertion; each was a correct answer to "did the files I read carry a problem",
reported as if it answered "is this repository sound".

## What to do instead

Ask what a green check read, not whether it was green. The cheap forms of that
question are:

    how many files did it open, and does the count match the tree
    which extensions does it select on
    which directory was it run from, and what is above that directory
    is the output capped
    has this check ever been seen failing for the reason it exists

A count is the most useful single answer, because it is comparable to something.
`52 source files` against a repository holding nine TypeScript sources and five
C++ ones is the whole finding, visible without reading the checker.

The standing hazard already recorded here, that a checker can pass while
asserting nothing, is the same failure seen from the checker's side. This is the
adopter's side: a checker that asserts perfectly over the wrong set.
