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

### ~~Go staying put is not a preference and must not be traded away~~ Wrong, corrected 2026-08-27

**That was my inference stated as a fact, and it was wrong.** What I was told was
that Go *helped answer* the lineage question, because nothing here was ever written
in Go. What I wrote was that bolt must therefore stay Go or the proof is spent.
That step was mine and nobody made it.

**The ruling, first-hand to bolt's session and recorded at bolt `2cbd872`:** bolt
is expected to be rewritten in Rust, the Go-as-provenance argument is not what the
choice rests on, and **qwark and grim stay Go to demonstrate working with Go.**

**Why it costs nothing, which is the part worth keeping.** The provenance is
carried by the *derivation record*, not by the language. `bolt/REQUIREMENTS.md`
opens by stating those requirements were reached from
`silo/docs/ARCHITECTURE.md` and from answers, with no earlier bolt implementation,
requirements document, design note or test read. That is a written chain, and a
Rust bolt translated from this one inherits it because this one's cleanliness is
**recorded rather than inferred from what it is written in**.

The language argument would only have been load-bearing if the derivation were not
written down. It is, thoroughly, so losing it costs nothing.

**The constraint that does not change:** the archived tree stays sealed. That is
what the derivation rests on and it is language-independent.

Go remains genuinely right for bolt on merit, and that is now the only claim being
made for it: subprocess orchestration, evidence collection, and a static binary
with no runtime to install.

### How this got corrected is worth more than the correction

bolt's session **asked the user directly rather than recording my relay**, on the
grounds that a ruling passed through another agent is second-hand and only the
agent in the conversation can cite the source. That is the right discipline and it
caught an error two sessions had already written down.

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
