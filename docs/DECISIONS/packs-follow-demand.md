# Packs follow demand

## The decision

A language gets a pack when something in the ecosystem needs to read or write a
structured file in it. Not before.

## Why

A pack is not free after it is written. It is a second implementation that every
schema change has to land in, a second suite that has to assert the same tables,
and a second thing that can be forgotten. `docs/LESSONS/` carries what forgetting
one costs, measured.

So the question for a new pack is not whether a language would be nice to
support. It is what is blocked without it.

## What each pack serves

| Pack | Serves | State |
|---|---|---|
| Go | `bolt.go`, the previous Go implementation | Built |
| Python | toolbox's adapters and checkers, and skid | Built |
| Rust | bolt, which is now a Rust implementation | Built |
| Ruby | the estate's Ruby tooling as it is written | Built 2026-09-07 |
| TypeScript | the estate's TypeScript tooling as it is written | Being built |

**The rule is relaxed, 2026-09-07, and the reason is that its cost premise no
longer holds.** The decision reasoned that a pack is expensive after it is
written, being a second implementation every schema change has to land in. That
was true of a pack carrying a hand-written emitter per format. It is not true of
what a pack is now.

`packs-agree-on-structure-not-on-bytes` retired the emitters. A pack is its
language's libraries, the four adapters, the error family and the two calls: the
Ruby pack is 535 lines including its suite. The calls, the seams and the error
kinds are fixed by the contract and do not move, so the only thing that reaches
a pack afterwards is a new or changed schema.

So the question stopped being "what is blocked without it" and became "is this a
language the estate writes tools in". **A library is still never why a pack does
or does not get built**, which is what the Ruby round trip established: it was
doubted because `json_schemer` sounded unsupported, and measuring showed it is
not.

Toolbox's checkers and adapters are not fixed to Python. Any of Go, Python, Rust
or TypeScript is allowed, so what needs a pack is a live question for toolbox
rather than a hypothetical.

## Which language the system reaches for

Chosen rather than derived, so there is nothing to be right about and it is not
re-argued from the measurements below.

    once per gate, write speed matters       Python
    per path, or a TUI, or a shipped binary  Rust
    bolt.go, wrench's Go pack, qwark, grim   Go

**Go stays where it already is and does not spread.** The system at large is
Python or Rust. qwark and grim stay Go to demonstrate working with it.

**Go being right for a runner is a claim on merit and nothing else.**
Subprocess orchestration, evidence collection, and a static binary with no
runtime to install. It is not a provenance argument: the cleanliness of bolt's
derivation is carried by its written derivation record, which states the
requirements were reached from the platform architecture and from answers with
no earlier implementation read. A translation inherits that, because the record
is written rather than inferred from the language. What the derivation does rest
on is the archived tree staying sealed, and that is language-independent.

**Rust covers what Go was being recommended for.** Both give a single static
binary with no interpreter to install, which is the failure this ecosystem keeps
hitting, and Rust starts marginally faster. What Go had over it was the build
loop, and that cost lands on whoever writes the tool rather than on everyone who
runs it.

### The measurements underneath

**For a checker the choice is mostly startup cost**, because a jig task using
`{each_path}` pays it once per file. A do-nothing program, mean of 20 runs on
this machine:

    rust binary   2ms      node    20ms
    go binary     3ms      python3 21ms, and 59ms once it imports wrench
                           deno    21ms

So a per-path checker wants a compiled binary and a once-per-gate checker does
not care.

**The build loop is the cost that lands on the author**, and for Go it is
smaller than it looks. bolt at 5,807 lines with dependencies: 110ms cold, 55ms
with no change, 22ms after editing one file. An equivalent Rust CLI with a
dependency tree is seconds rather than milliseconds incrementally, which is
asserted rather than measured. That is the trade this preference accepts.

## wrench is upstream of the checkers

Toolbox's adapters and checkers need upgrading to the interface defined for
them, and a solid pack in each language they are written in is a prerequisite.
So pack demand is not hypothetical. It is on the critical path for the gate every
project here runs, and it is chicken-and-egg with wrench's own gate, which needs
those same checkers.

`NEXT_STEPS.md` carries what follows from that.

## Retired requirement ID

This replaces FR-5.4. It stated a policy for choosing work rather than a
property of wrench, so no test could discharge it.
