# The gate asks every validator wrench binds, and requires them to agree

## The question this replaces

The gate validated the shipped schemas with `ajv`, chosen because it was an
implementation no pack binds. Adding a TypeScript pack put that at risk, since
TypeScript's obvious choice is `ajv`, and the gate would then be asking one of
wrench's own bindings whether wrench's schemas are valid.

The framing was too narrow. It treated independence as a property of one
designated outsider, so adding a language looked like it broke something.

## The decision

The gate asks every validator wrench binds and requires unanimity, plus at least
one implementation no pack binds.

That takes the weight off the TypeScript question. `ajv` becomes one of N
instead of the independent one, so a TypeScript pack binds what its ecosystem
expects and nothing has to move.

## Why unanimity is stronger than one outsider

The check this replaced ran ajv with `strict: false`, deliberately, because
wrench's schemas use union types and ajv's strict mode is a style opinion, not a
validity check. So it contributed exactly one implementation's reading of the
specification and nothing more. Several independent implementations agreeing
is more than that.

It also tests something the old shape did not: that every pack can actually
consume what wrench ships. A pack that cannot compile a shipped schema is a
defect the gate should catch, and asking each pack the question catches it.

## The outsider stays, and why

Unanimity alone could become unanimous agreement among wrench's own bindings,
which is exactly what the original check was built to avoid. Keeping at least one
implementation no pack binds means N-of-N can never quietly become N-of-wrench.

Whoever adds the fifth pack checks this again: a pack and the gate's independent
validator may never bind the same library.

## How it runs

`bin/test-schema-validity.py`, gate task `schemas-valid-to-every-validator`. Five
readers: the Go, Python, Rust and TypeScript packs' `compile_schema`, and
`@hyperjump/json-schema` 1.17.8, which no pack binds and which replaces `ajv` as
the outsider now that the TypeScript pack binds `ajv`.

Every one validates against the 2020-12 meta-schema it bundles, with no network.
Measured: the four packs answered correctly inside a sandbox whose proxy reports
any fetch to an unlisted host, and none was reported; hyperjump runs under deno
with network permission withheld, so it cannot fetch.

Each run also hands every reader two schemas that are not valid 2020-12, a
numeric `type` and a string `required`. A reader must refuse both, so one that
stopped checking fails the gate instead of reading as agreement.
