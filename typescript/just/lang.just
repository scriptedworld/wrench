# The TypeScript half for wrench/typescript.
#
# Everything runs with this directory as its base, so npm reads this pack's
# `package.json`, its lock file and its `node_modules`, and nothing here reaches
# a sibling.
#
# The pack is Node-first and runs under Deno. Node is what it is written and
# published for: one consumer runs serverless on GCP, where Cloud Functions runs
# Node natively and Deno needs a container. Deno is a runtime it also runs on,
# and `deno-test` below is what keeps that true rather than assumed.
#
# There is no shared TypeScript standard in toolbox yet, the way there is for
# Go, Python, Rust and C++, so `checks` names this pack's own tools directly.
# When that jig exists this file takes it and these lines go, the same way the
# Rust pack's cargo tasks will.
#
# The tasks themselves live in `package.json`, because that is where a Node
# project declares them and a person working here runs `npm test` without
# reading a Justfile. These recipes are the two-word interface over them, not a
# second definition of what they do.

# all the quality tooling, at this pack's own base
checks:
    @just format-check
    @just _lint
    @just _typecheck
    @just test
    @just deno-test
    @just _shipped-current

# eslint reads the rule set from `eslint.config.js`, so nothing about the
# standard is on this command line. The type-aware rules are on, which is why
# this is slower than a syntax-only linter and why it catches more.
_lint:
    npm run --silent lint

# The type check is the closest thing this pack has to a compiler, since Node
# runs TypeScript by stripping the types rather than checking them: nothing else
# would notice a type that stopped holding.
_typecheck:
    npm run --silent types

# `shipped.ts` is generated from `schemas/`, and the generator's `--check` is
# what stops the copy going stale. The Go and Python packs have the same task in
# their own shape, and Rust needs none because `build.rs` regenerates on every
# build.
_shipped-current:
    npm run --silent shipped:check

# the suite, under the runtime the pack is published for
test:
    npm test

# The same suite under the other runtime, so "it also runs on Deno" is a
# measurement rather than a claim.
#
# `--no-check` because the type check belongs to `tsc`, which `_typecheck` above
# runs. Deno reads `tsconfig.json` and applies its own bundled compiler to it,
# and the two cannot be satisfied at once: the `lib` and `types` settings tsc
# needs to see `@types/node` are exactly the ones that hide Deno's own globals
# from Deno. Measured both ways.

# the same suite under Deno, the runtime the pack also runs on
deno-test:
    deno test --no-check --allow-read --allow-write --allow-env

# Coverage is not gated here yet: `node --test --experimental-test-coverage`
# collects it, and no shared standard states the minimum for this language.
# Named so its absence is visible rather than looking like an oversight.

# no coverage minimum is declared for this language yet
coverage:
    @echo "no coverage minimum is declared for the TypeScript pack yet"

# formatting verified, nothing written
format-check:
    npm run --silent format:check

# formatting written
format:
    npm run --silent format

# Node runs TypeScript directly, so there is nothing to build ahead of time.
# What a published package would need is a separate question: a consumer on a
# Node older than 22.18 gets no type stripping and would need an emitted `dist/`.

# nothing is built
build:
    @echo "node runs TypeScript directly, so there is nothing to build"

# nothing is distributed
dist:
    @echo "the TypeScript pack is consumed from source, so there is nothing to distribute"

# The dependencies, which are what an install means for a Node project. `ci`
# and not `install`, so the lock file decides and a run here cannot quietly
# move a version.

# the declared dependencies, exactly as the lock file pins them
install:
    npm ci

# Remove run directories and coverage output. `node_modules/` is NOT here and
# must not be: it is this pack's installed artefact, and base.just's rule is
# that a clean leaves the installed artefact alone. `just install` is what
# refreshes it.

# remove run directories and coverage output
clean:
    rm -rf .bolt-*/ coverage/
