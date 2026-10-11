# Which JSON Schema library each pack binds

FR-5.2: each pack binds to its language's established JSON Schema implementation
instead of implementing the specification itself. This records which one, per
language, with what was measured.

wrench writes no validator and is not going to. Implementing the specification
is what this decision avoids, and `a-library-per-language-not-a-c-core` refuses a
C core for the same reason: the codecs are the easy half and validation is the
hard one, so a pack that implements it has traded a solved problem for an
unsolved one.

## The survey

Every language with a pack built or planned has a maintained implementation
covering the 2020-12 dialect wrench declares.

| Language | Library | 2020-12 | How that was established |
|---|---|---|---|
| Go | `santhosh-tekuri/jsonschema/v6` | yes | In use, `go/go.mod` |
| Python | `jsonschema` | yes | In use, `pyproject.toml` |
| Rust | `jsonschema`, `default-features = false` | yes | Measured, below |

A library is not why a pack does or does not get built. What each pack waits
for is a consumer, per `packs-follow-demand`.

Go was the one to check, since a gap there would have been a problem and not an
inconvenience. There is no gap. The library declares `Draft4`, `Draft6`,
`Draft7`, `Draft2019` and `Draft2020`, and implements the keywords that exist
only in 2020-12:

    grep -rhoE '"(prefixItems|unevaluatedItems|unevaluatedProperties|dependentSchemas|\$dynamicRef)"' \
        $(go env GOMODCACHE)/github.com/santhosh-tekuri/jsonschema/v6@v6.0.3/*.go

    "$dynamicRef" "dependentSchemas" "prefixItems"
    "unevaluatedItems" "unevaluatedProperties"

Rust binds `jsonschema` and not `boon`, on use and maintenance, not on which
draft a crates.io line names first:

    jsonschema   0.52.0   released 2026-08-26     84,216,384 downloads
    boon          0.6.1   released 2025-01-07        458,196 downloads

Nineteen months apart, and 184 times the use.

**Declare it `default-features = false`.** From the crate's own metadata:

    default        -> ["resolve-http", "resolve-file", "tls-aws-lc-rs", "idna"]
    resolve-http   -> ["reqwest", "dep:rustls"]

So the default build resolves `$ref`s over HTTP and from the filesystem, and
links a whole HTTP client and TLS stack to do it. A plain `jsonschema = "0.52"`
would put a network stack inside every consumer of the pack, which is reason
enough on its own.

It is not, however, what discharges FR-3.10.

Turning the features off looks like it gets FR-3.10 at compile time, which would
be stronger than a runtime refusal and would mean the Rust pack could not be
talked out of it. It does not, because Cargo unifies features across the whole
dependency graph. Any other crate in a consumer's build that enables
`jsonschema/resolve-http` enables it for wrench too, and nothing here would
notice. A guarantee that any dependency can switch off is only an accident of
what else happens to be in the build.

What discharges it is a retriever that refuses, installed unconditionally in
`rust/src/schema.rs`, whichever features are on. The crate ships an equivalent
`OfflineRetriever` and it is not used, because it is private to jsonschema and
its message is the crate's and not wrench's, which FR-2.11 does not allow to
cross the boundary.

`default-features = false` stays. Keeping `reqwest` and a TLS stack out of a
build that does not want them is worth the line. It is a dependency decision,
though, not a security one.

The three packs refuse by three mechanisms and reach the same place: Go installs
a loader, Python compiles against a registry with nothing else in it, Rust
installs a retriever. None of them has an escape hatch. The old asymmetry (one
pack stronger than the other two) was resolved by making the other two
structural, not by weakening Rust.

## So the CLI fallback is not needed

The fallback, if no common surface existed, was a JSON Schema CLI wrapping
whatever one language provides, with every pack shelling out to it. That is not
required, and the reasons it was dropped still apply:

- Every pack would depend on a process boundary for its central operation. A
  library call becomes a fork, an argv, a temporary file and a parse.
- It reintroduces what the C core was refused for. One implementation
  everything binds to, with the binding cost paid at runtime instead of link
  time, and a deployment story worse than cgo's.
- It would make wrench's own contract untestable in-process. FR-2.5a exists
  so a test can exercise validation against no filesystem at all.

If a further language ever has no maintained implementation, that language does not
get a pack before this decision is revisited. `packs-follow-demand` says a pack
waits for a consumer; this adds that it also waits for a library.

## The gate's validators are not bindings

`bolt.wrench-quality.yaml` asks every pack's binding and jschon whether each
file in `schemas/` is valid 2020-12. jschon is a checker of wrench's own schema
files, not part of any pack: nothing imports it, nothing shells to it at run
time, and it never sees a document a consumer wrote.

**A pack and the gate's independent validator may never bind the same library**,
and whoever adds a pack checks that again. The criterion is the implementation
and not the runtime, so two implementations in one language are as independent
of each other as two in different ones.

`the-gate-asks-every-validator-and-requires-agreement` has the shape the check
takes: every validator wrench binds is asked and must agree, plus at least one
implementation no pack binds, so unanimity cannot quietly become unanimity among
wrench's own bindings.

### Why jschon

Four candidates went through the gate's own harness with no network allowed,
each alone as the independent reader, against the four shipped schemas and the
two controls:

    candidate                    lang    result
    jschon 0.11.1                Python  passes, with the 2020-12 meta-schema
                                         it ships
    boon 0.6.1                   Rust    passes, with the meta-schema it ships
    kaptinlin/jsonschema 0.9.10  Go      cannot run: fetches the 2020-12
                                         meta-schema over https and carries
                                         only drafts 4, 6 and 7
    google/jsonschema-go 0.4.3   Go      refuses jig.schema.json, failing to
                                         load definitions.schema.json by $ref;
                                         carries no meta-schema in the library

Both Go candidates pass once handed a local copy of the meta-schema. That makes
the one document the check turns on a copy wrench vendored, chosen by the tree
being judged, which is weaker than an implementation bringing its own. boon
passes, and its author, santhosh kumar tekuri, wrote the Go pack's binding: the
same design and the same reading of the specification, and so the weakest
outsider of the four. jschon is Mark Jacobson's, and the Python pack's
`jsonschema` is a different project.

jschon's cost is its age, with no release since 2023-10-22. JSON Schema 2020-12
is a fixed dialect, so that matters only if it stops installing on a newer
Python. If it does, kaptinlin with a vendored meta-schema is the measured
fallback.

The Go pack refuses a schema whose `$ref` points outside the shipped set, and
jschon accepts one. That is by design: jschon checks a schema against the
meta-schema and does not resolve its references, and the Go pack's loader
resolves only the shipped schemas.
