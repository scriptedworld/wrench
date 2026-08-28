# A format carries a semver version, and a major gets its own schema file

Answers `clank/tasks/wrench/schemas/10-is-the-envelope-schema-versioned`, which
was deferred on 2026-08-26 and settled on 2026-08-27.

## What is built now

**An optional top-level `version`, a semver string**, on the envelope, jig and
manifest schemas. FR-3.9.

Optional is what makes it additive: every document written before the field
existed carries none, and absent means the document claims nothing rather than
claiming version zero. Nothing broke, including bolt, which builds against this
working tree.

The pattern is full semver, so `1.0.0-rc.1+build.5` passes and `1`, `1.0`,
`v1.0.0` and `01.0.0` do not.

**What the pattern is for is rejecting things that are not semver.** `1`, `1.0`,
`v1.0.0`, `01.0.0`, `latest`. Without it, `type: string` would accept every one of
them and the field would mean whatever a producer felt like.

An unquoted `version: 1.0` in a hand-written file is refused too, because YAML
reads it as a float and a float is not a string. **That is a corollary and not the
argument**: a well-formed semver has two dots, so it never parses as a float, and
FR-4.1 quotes every string wrench writes, so nothing wrench emits could hit it.
The case only exists for a file a person typed, and it is already covered by
`1.0` not being semver.

## The definitions format does not carry one

`definitions.schema.json` is an **open mapping**: `propertyNames` constrains the
shape of a key and every key is a placeholder name. Reserving `version` there
means a jig can never have a `{version}` placeholder, which is a real cost the
other three formats do not pay.

Put to bolt, which owns what a definitions file means. **Answered no on
2026-08-27, and the reasoning is better than the reasoning for asking.**

**definitions is the one shipped schema whose keys are entirely a user
namespace.** The envelope, jig and manifest all have named properties, so
`version` sits beside them and a reader tells metadata from content by looking. In
definitions every key is a placeholder name, so `version` would be **both at
once**, and nothing in the document would say which was meant.

`{version}` is an ordinary placeholder rather than a contrived one: a jig passing
a version to a tool is the common case, and reserving the name costs that.

**The FR-4.19 precedent does not carry, and that was my error in asking.** FR-4.19
reserves the names *bolt supplies*, because a redefined `{base_dir}` would
substitute somewhere other than where the command stands. That is a reservation
against collision with a value bolt provides. A format-version key is a different
kind of thing.

If versioning a definitions file ever matters it goes out of band, since
`bolt.<name>.definitions.yaml` already carries a name and has room.

## How versions map to files, when there is a second one

**One file per MAJOR version, with the major in the `$id`.**

    https://scriptedworld.github.io/wrench/v1/envelope.schema.json
    https://scriptedworld.github.io/wrench/v2/envelope.schema.json

Minor and patch get no file. Semver already says they are backward compatible, so
the v1 schema accepts every `1.x.y`, and a document declaring `1.4.0` validates
against the v1 file. A new file is exactly the signal that something broke.

Each versioned schema constrains `version` to its own major, so a document
claiming `2.0.0` is refused by the v1 schema rather than silently checked against
the wrong shape.

**Retiring a version deletes its file, and its `$id` is never reused.** That is
the same rule `docs/REQUIREMENTS/` applies to requirement ids, for the same reason:
reuse silently rewrites what every existing reference meant.

## Why not one file with the versions as a `oneOf`

This was the alternative and it is rejected. It looks economical and is not.

**It answers the wrong question.** `oneOf` makes a document valid if it matches
*any* version. What a consumer needs is whether the document is valid against the
version **it claims**. A v1 document with a v2-shaped field would pass, and the
mismatch that a version exists to expose is exactly what gets hidden.

**Error messages become unreadable.** A failure reports every branch that did not
match, so one wrong field in a three-version file produces three sets of errors
and no statement of which one you meant. wrench's errors travel inside envelopes
as evidence, so that cost lands on whoever is debugging, on another machine.

**The file grows without bound and nothing can be deleted.** A retired version
stays in the document because removing a branch changes the meaning of every other
branch's index in an error path.

**Schema-per-major is also what the specification does to itself.** JSON Schema
ships `https://json-schema.org/draft/2020-12/schema` as a file per draft, not one
file branching over all of them.

## Should a document also name its schema?

Raised as a third option: a top-level `schema` beside `version`, so the document
says which schema to validate it against. **Worth doing, and not the way it first
reads.**

**Do not let a document choose its own validator.** That is the failure mode. A
document naming the schema it validates against can name one that makes it valid,
and wrench's whole job is establishing that a file has the form its schema
declares. Input selecting its own check is not a check.

**So the caller keeps naming the schema, and the field is cross-checked.** FR-2.2
stays exactly as it is: validation sits in the signature and nothing reads or
writes without naming what the file must conform to. If the document *also* names
one and the two disagree, that is an error.

**That closes a hole FR-2.3 currently states as permanent:**

> The signature compels a schema, not the right one. Passing none is impossible;
> passing the wrong one is not, and no part of the library detects that.

A document carrying its own `$id` makes passing the wrong one detectable for every
document that carries one. FR-2.3 would go from "no part of the library detects
that" to "detected wherever the document says". That is a real improvement to the
contract rather than a convenience.

**It also makes `version` mostly redundant, and that is fine.** Once an `$id`
carries the major, `schema: .../v2/envelope.schema.json` says both what the format
is and which major. `version` still carries minor and patch, which no file
distinguishes, and a document may carry either or both.

**Not built.** It changes what every producer writes and what wrench does with it,
so it needs bolt's agreement rather than wrench's decision alone.
`clank/tasks/wrench/schemas/40-a-document-may-name-its-own-schema` carries it.

## What is deliberately not done yet

**The `$id`s do not carry `/v1/` today**, and the schemas are not split. There is
one version of every format, so a split would be a breaking change to every
consumer in exchange for nothing.

Changing an `$id` is not free: it is what errors are named by, what a `$ref`
resolves through, and what bolt embeds. So it happens when a second major is
actually needed, and this file is here so that decision is executed rather than
re-litigated.

**The trigger is the first change that is not additive.** Every change so far has
been, which is why this cost nothing to defer and costs nothing to defer further.
