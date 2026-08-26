# What is still open

`REQUIREMENTS.md` covers what the README, bolt's contract rows, silo's platform
decision and wrench's one inbox entry support. This is what remains.

Every question here carries the answer I would take if nobody says otherwise.
None of them blocks writing the Go pack, because each default is buildable and
each is reversible without touching the two calls. Say which ones are wrong.

Each row in section 7 of `REQUIREMENTS.md` stays `[?]` until the question behind
it is closed.

---

1. Which codecs ship? **Default: YAML only.** Every structured file in the
   ecosystem is YAML by the platform decision, so a second codec has no consumer
   today. The codec argument exists so adding one later is not a signature
   change, which it already achieves with one implementation in the box.
2. Which readers and writers ship? **Default: a local file reader and a local
   file writer, and nothing else.** Everything wrench serves reads and writes
   files on the same machine. A test substitutes its own reader, which FR-2.5a
   already requires be possible, so an in-memory one does not need shipping to
   be usable.
3. Are the schemas files an editor can be pointed at? **Default: yes, shipped as
   files, and each pack loads them from that same set rather than embedding its
   own copy.** A YAML language server given a JSON Schema gives completion and
   inline errors while a jig is being written, which is where a typo is
   cheapest to find. It also settles FR-3.2 by construction: there is one copy
   and the pack reads it.
   Open inside this: whether the Go pack embeds them at build time with
   `go:embed`, which keeps bolt a single static binary and still leaves the
   files present in the repository for an editor to use.
4. How does the Python pack reach `dotfiles/bin/setup`? **Default: declare
   `python3-yaml` as a prerequisite and import `yaml` by name.** FR-6.1 and
   FR-6.2 already fix the constraint; what is open is only whether that is
   enough or whether the pack gets vendored into dotfiles as well. Vendoring is
   the fallback, worth choosing rather than arriving at.
   Filed as `clank/inbox/wrench/python-library-runs-before-pip-exists/`, and
   nothing is blocked by it today because the manifests are still TOML and
   `tomllib` is in the standard library.
5. Where does the shared fixture set live, and what pins both packs to the same
   revision of it? **Default: in this repository, beside the schemas, with each
   pack's tests reading it from the tree rather than from a release.** One
   repository holds the schemas and every pack, so a fixture and the packs it
   judges move in one commit. This only becomes a real question if a pack ever
   ships from somewhere else.
6. Does a validation failure carry the schema path that failed, or only a
   message? **Default: the path.** FR-5.5 holds the packs level on error shape,
   which needs the shape to be structured enough to compare across two
   languages. A bare string differs by wording between implementations and
   makes the fixture set untestable.
7. Is the envelope schema versioned? Every producer and consumer in the
   ecosystem validates against it, and bolt records the question as FR-13.10.
   **No default.** It decides whether a schema change is a breaking change for
   everything at once, and that is worth an explicit answer rather than a
   convention arrived at.
