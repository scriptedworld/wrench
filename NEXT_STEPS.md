# What is still open

**The work is in `~/.projects/clank/tasks/wrench/`, not here.** This file carries
the context behind the open questions and nothing that is sized enough to be a
task.

`REQUIREMENTS.md` covers what the README, bolt's contract rows, silo's platform
decision and wrench's inbox entries support, plus what building both packs
settled.

---

## One open question

### ~~1. How does the Python pack reach `dotfiles/bin/setup`?~~ Answered 2026-08-26

**It does not, and it never needed to.** Nothing in `dotfiles/bin/` imports
wrench or reads YAML at any level; the manifests are TOML read with stdlib
`tomllib`; and wrench is installed via a `python_projects` list into mise's
Python, after mise exists.

So the question dissolved rather than being decided. No apt package is declared on
dotfiles' account, nothing is vendored, and `sudo apt install python3-jsonschema`
is no longer owed. FR-7.4 is retired as answered, and FR-6.1 and FR-6.2 keep their
property while losing the bootstrap justification that motivated them.

`docs/DECISIONS/the-pack-is-installed-after-mise-not-before.md` carries the
measurements, including what is still unverified about `python3-yaml` and what is
still owed by dotfiles.

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
