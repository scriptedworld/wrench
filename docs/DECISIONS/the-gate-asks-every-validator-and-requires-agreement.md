# The gate asks every validator wrench binds, and requires them to agree

## The decision

The gate asks every validator wrench binds and requires unanimity, plus at least
one implementation no pack binds.

Independence is not a property of one designated outsider. A pack binds what its
ecosystem expects, the gate asks it, and adding a language adds a reader rather
than breaking anything.

## Why unanimity is stronger than one outsider

One validator contributes exactly one implementation's reading of the
specification and nothing more. Several independent implementations agreeing
is more than that.

It also tests that every pack can actually consume what wrench ships. A pack
that cannot compile a shipped schema is a defect the gate should catch, and
asking each pack the question catches it.

## The outsider stays, and why

Unanimity alone could become unanimous agreement among wrench's own bindings.
Keeping at least one implementation no pack binds means N-of-N can never
quietly become N-of-wrench.

Whoever adds a pack checks this again: a pack and the gate's independent
validator may never bind the same library.

## How it runs

`bin/test-schema-validity.py`, gate task `schemas-valid-to-every-validator`. Four
readers: the Go, Python and Rust packs' `compile_schema`, and jschon 0.11.1,
which no pack binds.

Every one validates against the 2020-12 meta-schema it bundles, with no network.
Measured: every pack answered correctly inside a sandbox whose proxy reports
any fetch to an unlisted host, and none was reported. jschon ran with no
network allowed and nothing was reported; it reaches the network only through
`requests`, which the gate's `uv run --with jschon` does not install.

Each run also hands every reader two schemas that are not valid 2020-12, a
numeric `type` and a string `required`. A reader must refuse both, so one that
stopped checking fails the gate instead of reading as agreement.
