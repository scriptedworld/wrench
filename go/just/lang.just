# The Go half for wrench/go.
#
# Everything here runs with this directory as its base, which is what makes the
# pack's tooling the pack's own: `./...` is the module and nothing reaches a
# sibling. The jigs live at the repository root, so each bolt call carries
# `--config-dir ..`, and base's `_verdict` is variadic and takes it.
#
# `--definitions wrench` is what points the shared common jig at the contract,
# which is one copy at the repository root serving every pack rather than one
# per base that could drift. Without it the jig keeps its defaults and looks for
# REQUIREMENTS.md and SUPPRESSIONS beside this file, where neither is.
#
# The Go pack is a library, so `install` and `dist` have nothing to do: there is
# no binary to place and a Go module is consumed from its source by path or by
# version. `go-std-quality` covers format, tidy, build, vet, lint, tests with
# coverage, and known vulnerabilities, so the recipes below that a person runs
# while working are deliberately the same tools the gate reaches through bolt.

# This pack's tooling and nothing else. The contract checks that read every
# pack at once, traceability and suite parity among them, belong to the root and
# cannot run here: a row scoped to another pack has no test at this base by
# design, so asking for one from here fails for being asked in the wrong place.

# all the quality tooling, at this pack's own base
checks:
    @just _verdict go-std-quality --config-dir .. --definitions wrench

# The race detector needs cgo, and shuffling is what stops one test's leftovers
# passing for another's setup. Both are what the jig runs, named here so running
# the piece alone asks the same question the gate does.

# the suite
test:
    CGO_ENABLED=1 go test -race -shuffle=on ./...

# The jig enforces the minimum per file through an adapter. `go test -cover`
# here instead prints numbers and fails on nothing.

# the suite with coverage, and the minimum enforced
coverage:
    @just _verdict go-std-quality --config-dir .. --definitions wrench

# gofmt lists unformatted files on stdout and exits 0 whatever it finds, so its
# exit status answers "did gofmt run" and never "is this formatted". `test -z`
# on its output is what makes this a check.

# formatting verified, nothing written
format-check:
    @out="$(gofmt -l .)"; \
    if [ -n "$out" ]; then echo "not gofmt-clean:"; echo "$out"; exit 1; fi

# formatting written
format:
    gofmt -w .

# everything in the module compiles
build:
    go build ./...

# nothing is distributed
dist:
    @echo "the Go pack is consumed as a module, so there is nothing to build"

# nothing is installed
install:
    @echo "the Go pack is consumed as a module, so there is nothing to install"

# The build cache is Go's own and lives outside the tree, so there is nothing
# here to remove but past run directories.

# remove run directories
clean:
    rm -rf .bolt-*/
