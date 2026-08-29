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

That makes the TypeScript question stop being load-bearing. `ajv` becomes one of
N rather than the independent one, so a TypeScript pack binds what its ecosystem
expects and nothing has to move.

## Why unanimity is stronger than one outsider

The existing check runs ajv with `strict: false`, deliberately, because wrench's
schemas use union types and ajv's strict mode is a style opinion rather than a
validity check. So today it contributes exactly one implementation's reading of
the specification and nothing more. Several independent implementations agreeing
is more than that.

It also tests something the old shape did not: that every pack can actually
consume what wrench ships. A pack that cannot compile a shipped schema is a
defect the gate should catch, and asking each pack the question catches it.

## The outsider stays, and why

Unanimity alone could become unanimous agreement among wrench's own bindings,
which is the thing the original check existed not to be. Keeping at least one
implementation no pack binds means N-of-N can never quietly become N-of-wrench.

Whoever adds the fifth pack checks this again: a pack and the gate's independent
validator may never bind the same library.

## What is not settled

Whether each pack can validate a schema against the 2020-12 meta-schema without
reaching the network, which is what "is this a valid schema" means. Every
binding embeds a meta-schema, and none of them has been asked this question
here.

The unanimity check is unwritten. The decision is what shape it takes; the task
is `schemas/50`.
