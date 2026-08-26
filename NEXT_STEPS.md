# What is still open

**The work is in `~/.projects/clank/tasks/wrench/`, not here.** This file carries
the context behind the open questions and nothing that is sized enough to be a
task.

`REQUIREMENTS.md` covers what the README, bolt's contract rows, silo's platform
decision and wrench's inbox entries support, plus what building both packs
settled.

---

## Two open questions

Both are tasks in `.questions` state, because each needs an answer before it can
be specified. The context is here; the task is the queue.

### 1. How does the Python pack reach `dotfiles/bin/setup`?

`clank/tasks/wrench/packaging/10-how-the-python-pack-reaches-bootstrap.questions`

**Default: declare the apt packages as prerequisites and import by name.**

Sharpened 2026-08-26 by building the pack: it needs `python3-jsonschema` as well
as `python3-yaml`, and that one is not installed here. The pack imports on mise's
interpreter, which has both, and not on `/usr/bin/python3`, which has neither
validation nor a way to get it without apt. So the prerequisite is two packages,
not one, and the bootstrap window is the case that has neither.

FR-6.1, FR-6.2 and FR-6.2a fix the constraint. What is open is only whether that
is enough, or whether the pack gets vendored into dotfiles as well. **Vendoring is
the fallback, worth choosing rather than arriving at.**

Nothing is blocked by it today, because the manifests are still TOML and
`tomllib` is in the standard library.

Owed to a person, since a Claude shell cannot run it:

    sudo apt install python3-jsonschema

`packages.toml` already declares `python3-yaml` for the bootstrap window with the
reasoning beside it. This is its sibling and it is one line with an exact
precedent.

### 2. Is the envelope schema versioned?

`clank/tasks/wrench/schemas/10-is-the-envelope-schema-versioned.questions`

Every producer and consumer in the ecosystem validates against it, and bolt
records the question as FR-13.10. **No default**, deliberately: it decides whether
a schema change is a breaking change for everything at once, and that is worth an
explicit answer rather than a convention arrived at.

The schema carries an `$id` today and no version, so the current answer is "not
versioned" by omission, which is the state this question exists to replace with a
decision.

This got sharper on 2026-08-26. The shipped schemas now reference each other by
`$id`, so a versioning scheme has to say what a `$ref` between two versioned
schemas means, and bolt builds against this working tree through a `replace`
directive, so "breaking" already has a live consumer to break.

---

## Where the rest went

Content that used to sit here has moved to where it is read rather than found:

| Was here | Now |
|---|---|
| Why a library per language, and cgo's cost | `docs/DECISIONS/a-library-per-language-not-a-c-core.md` |
| A pack is written from the contract | `docs/DECISIONS/a-pack-is-written-from-the-contract.md` |
| Packs follow demand | `docs/DECISIONS/packs-follow-demand.md` |
| A pack's spelling of the two calls | `docs/DECISIONS/each-pack-spells-the-calls-its-own-way.md` |
| Map keys are emitted in sorted order | `docs/DECISIONS/canonical-form-sorts-map-keys.md` |
| Six rows no test can cite | Resolved. Four retired to `docs/DECISIONS/`, two covered when the Python pack landed. `REQUIREMENTS.md` records both. |
