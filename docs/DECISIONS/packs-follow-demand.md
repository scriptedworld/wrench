# Packs follow demand

## The decision

A language gets a pack when something in the ecosystem needs to read or write a
structured file in it. Not before.

## Why

A pack is not free after it is written. It is a second implementation that every
schema change has to land in, a second suite that has to assert the same tables,
and a second thing that can be forgotten. `docs/LESSONS/` carries what forgetting
one costs, measured.

So the question for a new pack is not "would this language be nice to support"
but "what is blocked without it".

## What each pack serves

| Pack | Serves | State |
|---|---|---|
| Go | bolt, which reads and writes every structured file through it | Built |
| Python | toolbox's adapters and checkers | Built |
| Rust | Consumer not yet identified here | Not built |
| TypeScript | Consumer not yet identified here | Not built |
| Ruby | Consumer not yet identified here | Not built |

**Three unbuilt packs are in the same state**, waiting on a consumer rather than on
a decision or a library. Ruby was dropped and restored on 2026-08-27, and the
round trip is worth keeping: it was doubted because `json_schemer` **sounded**
unsupported, and measuring showed it is not. **A library is never why a pack does
or does not get built.**

FACT 2026-08-27: there is no Ruby anywhere in `~/.projects`, and the option is
kept open anyway. Absence is the current condition rather than a verdict.

**Toolbox's checkers and adapters are not fixed to Python.** Any of Go, Python,
Rust or TypeScript is allowed, stated 2026-08-27, so "what needs this" is a live
question for toolbox rather than a hypothetical for the two unbuilt packs.

### PREFERENCE 2026-08-27: Python or Rust, not Go everywhere

**Go stays where it already is and does not spread.** bolt is Go, wrench's first
pack is Go, and some tooling is wanted as a deliberate example of working with it.
**The system at large should be Python or Rust.**

Which way the system goes is a preference, chosen rather than derived, so there is
nothing to be right about and it is not re-argued from the numbers below.

**Go staying put is not a preference, and this half must not be traded away.**
FACT 2026-08-27, from the user: **nothing in this ecosystem was ever written in
Go**, so a Go implementation cannot plausibly be a derivation of the archived bolt.
The language choice is itself a clean-room proof, made to answer "was this based on
former code" rather than on technical fit.

**That proof holds only while bolt stays Go.** A port to Rust could be alleged to
be a translation of the Go one, so the argument would be spent rather than kept.
Anyone reading the preference above and proposing to port bolt, on the reasonable
grounds that Rust does subprocess orchestration perfectly well, would be
destroying something not visible in the code.

The two reasons happen to agree. Go is also genuinely right for bolt: subprocess
orchestration, evidence collection, and a single static binary with no runtime to
install, which is the property that made a dangling `~/bin/bolt` a one-line fix
rather than an install problem. **Only one of those reasons survives a rewrite.**

What follows from it:

    once per gate, write speed matters       Python
    per path, or a TUI, or a shipped binary  Rust
    bolt, wrench's Go pack, worked examples  Go

**Rust covers what Go was being recommended for.** Both give a single static
binary with no interpreter to install, which is the failure this ecosystem keeps
hitting, and Rust starts marginally faster. What Go had over it was the build
loop, and that is a cost paid by whoever writes the tool rather than by everyone
who runs it.

### The measurements the preference sits on top of

**For a checker the choice is mostly startup cost**, because a jig task using
`{each_path}` pays it once per file. FACT 2026-08-27, do-nothing program, mean of
20 runs on this machine:

    rust binary   2ms      node    20ms
    go binary     3ms      python3 21ms, and 59ms once it imports wrench
                           deno    21ms

So a per-path checker wants a compiled binary and a once-per-gate checker does
not care.

**The build loop is the cost that lands on the author**, and for Go it is smaller
than it looks. FACT 2026-08-27, bolt at 5,807 lines with dependencies: 110ms cold,
55ms with no change, **22ms after editing one file**. CLAIM: an equivalent Rust CLI
with a dependency tree is seconds rather than milliseconds incrementally. That is
the trade the preference accepts.

## wrench is upstream of the checkers

CLAIM 2026-08-26: toolbox's adapters and checkers need upgrading to the interface
defined for them, and a solid pack in each language they are written in is a
prerequisite for that work. So pack demand is not hypothetical. It is on the
critical path for the gate every project here runs, and it is chicken-and-egg
with wrench's own gate, which needs those same checkers.

`clank/tasks/wrench/` carries what follows from that.

## Retired requirement ID

This replaces FR-5.4, retired 2026-08-26. It stated a policy for choosing work
rather than a property of wrench, so no test could discharge it.
