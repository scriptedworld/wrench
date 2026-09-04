# Security

## Reporting a vulnerability

Report privately through GitHub, on the Security tab, using Report a
vulnerability. That opens an advisory visible to the maintainers and to you, and
it is the reporting route. Do not open a public issue for something exploitable.

Say what you fed wrench, which pack, and what happened. A document that
reproduces it is worth more than a description of one.

## Where the trust boundary is

wrench reads bytes it did not produce and hands back a structure, so the case
that matters is a document arriving from somewhere the caller does not control.

Parsing is meant to fail rather than to surprise. Bytes that are not the format
they were read as produce a `parse` error, and every failure crossing the
boundary is one of wrench's seven error kinds. A crash, a hang, or anything
executing out of a document's contents is what this file is for. The Python pack
decodes YAML with `yaml.safe_load`, which constructs no arbitrary objects.

Schema references resolve locally and nowhere else. A `$ref` reaches the shipped
schemas and the document's own fragments, and everything else is refused: a
`file://` URL, an `http` or `https` URL, a bare absolute path, a relative path.
Each of those loads off disk or opens a socket under the bound validators' own
resolution, which is why the refusal exists. **There is no way to ask for more**,
in any pack, from any environment.

**The refusal is judged on the resolved reference and not on what was written.**
A relative `$ref` resolves against the document's `$id`, so the same text is a
different reference in a different document. Measured 2026-09-03:
`/tmp/x.schema.json` under an `$id` of `https://elsewhere.invalid/root.json`
resolves to `https://elsewhere.invalid/tmp/x.schema.json`, and under a schema
declaring no `$id` at all it is a path. A check reading the text would answer
about the wrong thing.

Each pack refuses by a different mechanism and the refusal is the same. Go
installs a loader that returns wrench's message, Python compiles against a
registry holding only the shipped set so retrieval is never reachable, and Rust
installs a retriever that refuses.

**Rust's `default-features = false` is not the refusal, and reading it as one was
a mistake this file used to make.** Declaring `jsonschema` without
`resolve-http` and `resolve-file` keeps an HTTP client and a TLS stack out of a
build that does not otherwise want them, which is worth having. It does not stop
resolution: **Cargo unifies features across the whole dependency graph**, so any
other crate in a consumer's build that enables `jsonschema/resolve-http` enables
it for wrench too, silently. The retriever is what holds regardless.

**A keyword in an instance is data.** `$ref`, `$id` and `$schema` are keywords in
a schema and ordinary keys in the document being validated, and nothing
interprets them there. Measured in all three packs against a `file://` reference
whose target existed on disk: accepted, unread. A document of yours may carry
those keys.

Validation establishes form and not meaning. A document that validates has the
shape its schema declares; whether its values are safe to act on belongs to the
consumer.

wrench imposes no size or nesting limit of its own. A document goes to the bound
parser as it stands, so a caller reading from an untrusted source bounds what it
is willing to read before wrench sees it.
