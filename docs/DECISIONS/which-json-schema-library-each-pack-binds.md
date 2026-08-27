# Which JSON Schema library each pack binds

FR-5.2: **each pack binds to its language's established JSON Schema
implementation rather than implementing the specification itself.** This records
which one, per language, with what was measured.

**wrench writes no validator and is not going to.** Implementing the
specification is the thing this decision exists to avoid, and
`docs/DECISIONS/a-library-per-language-not-a-c-core.md` says why a C core was
refused for the same reason: the codecs are the easy half and validation is the
hard one, so a pack that implements it has traded a solved problem for an
unsolved one.

## The survey

FACT 2026-08-27. Every language with a pack built or planned has a maintained
implementation covering the 2020-12 dialect wrench declares.

| Language | Library | 2020-12 | How that was established |
|---|---|---|---|
| Go | `santhosh-tekuri/jsonschema/v6` | yes | In use, `go.mod` |
| Python | `jsonschema` | yes | In use, `pyproject.toml` |
| Rust | `boon` 0.6.1 | yes | Its crates.io description |
| TypeScript | undecided, `ajv` or `@hyperjump/json-schema` | both yes | Both run against wrench's schemas 2026-08-27 |
| Ruby | `json_schemer` 2.5.0 | yes | The gem's own summary |

**A library is not why a pack does or does not get built.** Ruby was dropped and
restored on 2026-08-27, and `json_schemer` was solid throughout: 76,948,643 total
downloads, 6,792,182 on 2.5.0, MIT, released 2025-12-09. What each pack waits for
is a consumer, per `docs/DECISIONS/packs-follow-demand.md`.

**Two library names were doubted for sounding unsupported**, `json_schemer` and
`ajv`, and both turned out to be first class when measured. That is the reason
this table carries numbers rather than adjectives.

**Go was the one worth checking**, since a gap there would have been a problem
rather than an inconvenience. It is not a gap. The library declares `Draft4`,
`Draft6`, `Draft7`, `Draft2019` and `Draft2020`, and implements the keywords that
exist only in 2020-12:

    grep -rhoE '"(prefixItems|unevaluatedItems|unevaluatedProperties|dependentSchemas|\$dynamicRef)"' \
        $(go env GOMODCACHE)/github.com/santhosh-tekuri/jsonschema/v6@v6.0.3/*.go

    "$dynamicRef" "dependentSchemas" "prefixItems"
    "unevaluatedItems" "unevaluatedProperties"

**Ruby.** `json_schemer`'s summary: *"JSON Schema validator. Supports drafts 4, 6,
7, 2019-09, 2020-12, OpenAPI 3.0, and OpenAPI 3.1."* Versions run to 2.5.0.

**Rust.** `boon`'s crates.io line: *"JSONSchema (draft 2020-12, draft 2019-09,
draft-7, draft-6, draft-4) Validation"*. `jsonschema` 0.52.0 is the alternative
and the choice can wait for whoever writes the pack.

## So the CLI fallback is not needed

The fallback, if no common surface existed, was a JSON Schema CLI wrapping
whatever one language provides, with every pack shelling out to it. **That is not
required**, and it is worth writing down why it was considered and dropped:

- **Every pack would depend on a process boundary** for its central operation.
  A library call becomes a fork, an argv, a temporary file and a parse.
- **It reintroduces what the C core was refused for.** One implementation
  everything binds to, with the binding cost paid at runtime instead of link
  time, and a deployment story worse than cgo's.
- **It would make wrench's own contract untestable in-process.** FR-2.5a exists so
  a test can exercise validation against no filesystem at all.

If a fifth language ever has no maintained implementation, **that language does
not get a pack** before this decision is revisited.
`docs/DECISIONS/packs-follow-demand.md` already says a pack waits for a consumer;
this adds that it also waits for a library.

## ajv is not one of these, and is not a binding

`bolt.wrench-quality.yaml` runs `ajv` over `schemas/*.schema.json` in the gate.
**That is a checker of wrench's own schema files, not part of any pack.** No pack
imports it, nothing shells to it at runtime, and it never sees a document a
consumer wrote.

It is there because both packs compiling their own schemas cannot catch both
bindings misreading the specification the same way, and JavaScript is the only
runtime with no wrench pack planned, so it stays a second opinion.
`clank/tasks/wrench/schemas/20-an-independent-validator-checks-the-schemas.complete`
has the reasoning and the alternatives that were measured.
