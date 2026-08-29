# What is still open

**The work is in `~/.projects/clank/tasks/wrench/`, not here.** This file carries
the context behind the open questions and nothing that is sized enough to be a
task.

## A handoff writes two files and stops

Ruled by our user 2026-08-29. Above the context threshold the permitted set is
the prepare-clear skill, `START_HERE.md` and `NEXT_STEPS.md`. Nothing else: no
commits, no writes into clank, no gate runs, no inbox entries.

**This needs to reach the standing rules**, since it is true of every repository
and is only recorded here and in `START_HERE.md` today. It is silo's to write,
and the session that would have filed it against silo was the one being stopped.
Raise it when a session is next below the threshold and free to file.

The related finding is already at
`clank/inbox/silo/a-session-ran-past-90-percent-without-stopping`, which asks who
enforces the threshold and carries our user's proposal that grim deny tool use
above it. **That entry does not yet carry this three-item permitted set**, which
is the concrete answer to the wrinkle it names about a handoff needing tools.

### Our user's reading: this is grim's starter rule

The wrinkle that entry raises is that grim would have to recognise a handoff
rather than trust a session claiming to do one. **The three-item set removes
that.** It is a whitelist of two literal paths and one skill, not a mode:

    context_percent >= threshold
        allow   Write/Edit to START_HERE.md and NEXT_STEPS.md
        allow   the prepare-clear skill
        deny    everything else

Both paths are repository-root files with fixed names, so the rule is a string
comparison. Nothing has to infer intent, and a session cannot talk its way past
it, which is the property rule 4a asks for and that a session judging itself
does not have.

It is also a good first rule because the failure is loud and safe. A session
denied everything but its handoff is visibly stopped rather than reading as
`idle`, and the worst outcome of a false positive is a handoff written early.

**grim owns the mechanism, silo owns the threshold and the rule.** Neither is
wrench's. File both when a session is below the line and free to.

`docs/REQUIREMENTS/` covers what the README, bolt's contract rows, silo's platform
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
measurements. **`python3-yaml` is settled since 2026-08-28**: artefact, not
floor. It is llvm's dependency and only the declaration was ever dotfiles',
undeclared at their `bf38481` and correctly left installed. Nothing is owed by
dotfiles on wrench's account.

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

## Three codecs ship, and what the JSON one cost

**Both JSON and TOML were wanted**, ruled 2026-08-27, and both shipped at
`5b2c397`. What is kept here is the reasoning a fourth format would need.

**JSON was called near-free and was not.** The decoded value type already *is*
JSON in every pack (`map[string]any`, `dict`, `serde_json::Value`), so no
coercion was needed and FR-2.9's reconciliation problem did not arise. That much
held. What it hid is that binding a standard library for the emitter buys its
opinion about how a number is spelled, and the three libraries disagreed with
each other and with the two codecs each pack had already hand-written. FR-4.8
and `7076801` settle it.

**So the cheapness of a codec is about its value type, not its emitter.** A
fourth format should expect to hand-emit whatever the contract has an opinion
about, however complete the library looks.

**A codec refuses a value it cannot write, using the error every pack already
raises.** Not a schema check. FR-4.1 already says a value with no canonical form
is refused, and all three packs already raise a per-key encode error:

    EncodeError: wrench: encoding f.yaml: at key "c":
                 cannot write object in canonical form

A null in TOML is that rule with a different noun, so it needs no new mechanism.
Walking the schema for features a codec cannot express was considered and
refused: a permissive schema permits a null without requiring one, so TOML would
only work against a schema written to exclude what TOML cannot hold, which makes
a caller annotate a schema to satisfy a serialisation format.

**TOML has two limits and both are the format's, not a library's.** Measured with
`tomlkit` 0.15.1: a null anywhere is refused, and any root that is not a table is
refused, so a top-level array, string, number or bool is out. TOML has no null
type in its specification and a document is a table by definition. Everything else
is expressible, including mixed arrays, arrays of tables, whole floats and
integers past 2^63. The probes are beside the task.

**The Python pack takes no TOML writer.** `tomllib` is stdlib, parses, and has no
`dumps`, which is sufficient because wrench binds a parser and hand-emits
canonical form in every pack already. Its dependency footprint is the stated
reason infobot declined to import wrench, so a writer only one codec needs would
add to exactly that cost.

**A native TOML date decodes to its ISO 8601 string**, which is FR-2.9 answering
it: a lossless spelling, and the same rule that turns a YAML timestamp into a
string. Asserted in all three suites.

## Two questions are open, and neither is wrench's alone

They live as tasks rather than here, because each needs somebody else:

    schemas/40  Should a document name its own schema, cross-checked rather
                than trusted. It closes the hole FR-2.3 states as permanent.
                bolt has agreed; the cost lands on every adapter that writes
                an envelope, and toolbox has not been asked.

    schemas/50  A TypeScript pack would bind ajv, which the gate uses as its
                independent check. One of the two has to move before that
                pack is written.

---

## The gate is green, and the documents are behind the standard

**`bolt wrench-quality .` reports `"success": true`.** Everything the shared
Python standard found when the pack was wired to it is cleared and none of it was
silenced; `clank/tasks/wrench/gate/30` carries what each category was. Two lines
carry a bandit pragma, registered in `SUPPRESSIONS` with the question and the
answer, and the register is checked since toolbox `6ac4304`.

bandit's 44 `assert_used` findings in a pytest suite are the shared jig's shape
rather than wrench's debt and are routed to silo. They are skipped by the jig
itself, on its own reasoning, and no pragma here touches them.

**These documents do not meet `silo/docs/PATTERNS/writing-standard.md`.**
Measured 2026-08-27: 17 date-stamped statements in `docs/PROJECT.md`, strikethrough
corrections in two files under `docs/DECISIONS/`, and the machine tells item 5
lists, including bold on a phrase in most paragraphs. Item 3 says git holds the
history and item 4 says a mistake worth keeping goes in `docs/LESSONS/` once,
without the blow-by-blow.

Four kinds of date are exempt and stay: a statement of where work came from, a
version boundary, content a requirement mandates, and a date inside quoted output.
Read the standard before sweeping, because a rewrite pass has already eaten a
load-bearing provenance line in another repository under this rule.

## Where the rest went

Content that used to sit here has moved to where it is read rather than found:

| Was here | Now |
|---|---|
| Why a library per language, and cgo's cost | `docs/DECISIONS/a-library-per-language-not-a-c-core.md` |
| A pack is written from the contract | `docs/DECISIONS/a-pack-is-written-from-the-contract.md` |
| Packs follow demand | `docs/DECISIONS/packs-follow-demand.md` |
| A pack's spelling of the two calls | `docs/DECISIONS/each-pack-spells-the-calls-its-own-way.md` |
| Map keys are emitted in sorted order | `docs/DECISIONS/canonical-form-sorts-map-keys.md` |
| Six rows no test can cite | Resolved. Four retired to `docs/DECISIONS/`, two covered when the Python pack landed. `docs/REQUIREMENTS/` records both. |
