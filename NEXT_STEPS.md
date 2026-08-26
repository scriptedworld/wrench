# What is still open

`REQUIREMENTS.md` covers what the README, bolt's contract rows, silo's platform
decision and wrench's one inbox entry support, plus what building the Go pack
settled. This is what remains.

Building answered five of the seven questions that stood here, because a
decision you have to make to write the code is one you have made by writing it.
Each is now a row: FR-2.7 the shipped codec, FR-2.8 the shipped reader and
writer, FR-3.5 the schemas as files, FR-5.6 where the fixture set lives, and
FR-2.6 what a failure says.

---

# Still open

1. How does the Python pack reach `dotfiles/bin/setup`? **Default: declare
   `python3-yaml` as a prerequisite and import `yaml` by name.** FR-6.1 and
   FR-6.2 fix the constraint; what is open is only whether that is enough or
   whether the pack gets vendored into dotfiles as well. Vendoring is the
   fallback, worth choosing rather than arriving at.
   Nothing is blocked by it today because the manifests are still TOML and
   `tomllib` is in the standard library.
2. Is the envelope schema versioned? Every producer and consumer in the
   ecosystem validates against it, and bolt records the question as FR-13.10.
   **No default.** It decides whether a schema change is a breaking change for
   everything at once, and that is worth an explicit answer rather than a
   convention arrived at.
   The schema carries an `$id` today and no version, so the current answer is
   "not versioned" by omission, which is the state this question exists to
   replace with a decision.

---

# Six rows no test can cite, and why

The traceability gate reports them. They are left visible rather than turned
green, because the reason differs by row and only one of the two is a gap.

**FR-6.1 and FR-6.2 are the Python pack's.** They are real requirements on
wrench and the Go pack cannot discharge them. They get covered when the Python
pack exists, and until then the gate is right to say nobody holds them.

**FR-5.1, FR-5.1a, FR-5.3 and FR-5.4 state why the project is shaped as it is,
not a property of a pack.** A library per language rather than a C core, what
cgo would cost, that a pack is written from the contract rather than by reading
another one, and that packs follow demand. No test can discharge any of them,
because none of them is a claim about what the code does.

The ecosystem's own split says `REQUIREMENTS.md` states what must be true and
design notes say why. Those four are design notes sitting in a requirements
table. Moving them needs a `docs/` tree, which wrench does not have yet, so it
waits for `/commission` rather than being done by half.

---

# Known and not decided

**A pack's spelling of the two calls.** The contract names them
`load_formatted_file` and `save_formatted_file`. The Go pack exports
`LoadFormattedFile` and `SaveFormattedFile`, because a pack spells things the
way its own language spells them and what the packs share is behaviour. Said
here so the Python pack does not read the Go one and conclude the names drifted.

**Map keys are emitted in sorted order.** A YAML mapping has no order of its
own and a Go map has none either, so sorting is what makes two runs over the
same structure produce the same bytes. A pack whose language preserves
insertion order has to sort anyway to stay level, and the fixture set is what
catches it if one does not.
