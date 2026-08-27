# What is still open

**The work is in `~/.projects/clank/tasks/wrench/`, not here.** This file carries
the context behind the open questions and nothing that is sized enough to be a
task.

`REQUIREMENTS.md` covers what the README, bolt's contract rows, silo's platform
decision and wrench's inbox entries support, plus what building all three packs
settled.

---

## Questions, answered and open

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

### ~~2. Is the envelope schema versioned?~~ Answered 2026-08-27

**Yes.** An optional top-level `version`, a semver string, on the envelope, jig and
manifest. Optional is what made it additive, so nothing broke.

Not on `definitions`, and bolt's reasoning for that is the one to keep: it is the
only shipped schema whose keys are entirely a user namespace, so `version` would
be metadata and a placeholder name at once. `{version}` is an ordinary placeholder.

`docs/DECISIONS/a-format-carries-a-semver-version.md` carries it, including the
layout for when a second major exists: one file per major with the major in the
`$id`, and why a single file branching over versions with `oneOf` is refused.

---

## Three questions are open, and none is wrench's alone

They live as tasks rather than here, because each needs somebody else:

    codecs/10   JSON and TOML beside YAML, with per-format wrappers over the
                two calls. TOML cannot represent null and has native dates
                that are not JSON types, and Python's tomllib is read-only.

    schemas/40  Should a document name its own schema, cross-checked rather
                than trusted. It closes the hole FR-2.3 states as permanent.
                bolt has agreed; the cost lands on every adapter that writes
                an envelope, and toolbox has not been asked.

    schemas/50  A TypeScript pack would bind ajv, which the gate uses as its
                independent check. One of the two has to move before that
                pack is written.

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
