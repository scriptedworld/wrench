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

Schema references resolve locally and nowhere else. A `$ref` reaches the four
shipped schemas and the document's own fragments, and anything else is refused,
including a `file://` URL and a bare absolute path. Both of those load off disk
under the bound validators' own resolution, which is why the refusal exists.

`WRENCH_ALLOW_EXTERNAL_SCHEMA_REFS=1` turns the refusal off in the Go and Python
packs and restores whatever the bound library does, which includes reading files
named by a document. It is there to unblock a caller who has no other route, and
it is not a supported mode: the Python binding already calls that behaviour a
vulnerability and is removing it. The Rust pack cannot offer the switch, because
`jsonschema` is built with `default-features = false` and the resolving code is
never linked.

Validation establishes form and not meaning. A document that validates has the
shape its schema declares; whether its values are safe to act on belongs to the
consumer.

wrench imposes no size or nesting limit of its own. A document goes to the bound
parser as it stands, so a caller reading from an untrusted source bounds what it
is willing to read before wrench sees it.
