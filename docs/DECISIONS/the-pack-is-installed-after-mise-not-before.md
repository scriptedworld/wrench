# The Python pack is installed after mise, not before it

Answers FR-7.4, which asked how the pack reaches its bootstrap consumer. **It has
no bootstrap consumer**, so the question dissolved rather than being decided.

## What was believed

wrench's FR-6.1 and FR-6.2 were written on the premise that `dotfiles/bin/setup`
runs on `/usr/bin/python3` before mise, uv or pip exist, and would want to read a
manifest through this pack. A pack needing `pip install` first would have meant
installing requires the installer, so the pack was shaped to import by name and
survive on whatever apt supplied.

That premise drove a real constraint: two apt packages the bootstrap window did
not have, and a fallback option of vendoring the pack into dotfiles.

## What is actually true

FACT 2026-08-26, measured in `~/.projects/dotfiles` at `6d00d2d`:

- **Nothing in `bin/` imports `yaml`**, at any level, lazy or otherwise.
  `grep -rnE 'import yaml|yaml\.safe_load|yaml\.load' bin/` returns nothing.
- The manifests are TOML and `bin/_pkg.py` reads them with stdlib `tomllib`,
  which is the stated reason they are TOML: the tool that installs everything
  must not itself need something installed first.
- The only YAML in that repository is `bolt.*.yaml`, read by `bolt`, which is a
  Go binary. No Python touches it.

So the bootstrap window needs no YAML, no validation, and nothing from wrench.

## The route, and it is after mise

CLAIM 2026-08-26, from the dotfiles session relaying the user: wrench is installed
via a `python_projects` list into the standard mise-managed Python, or via
`uv tool` if it is ever a tool rather than a module to be imported. **Both land
after mise exists.**

Marked CLAIM rather than FACT because it is intent relayed at one remove, and
because the list does not exist yet: FACT 2026-08-26, `python_projects` has never
appeared in `packages.toml`, on any branch, in any commit.

## What this changes here

**FR-6.1 and FR-6.2 keep their property and lose their justification.** Importing
by name and running from a source checkout are still true and still wanted; they
are now wanted because the pack reads `schemas/` from the repository and so must
be installed editable, not because an interpreter without pip has to cope.

**Nothing gets declared or vendored on dotfiles' account.** Not `python3-yaml`,
not `python3-jsonschema`, and no vendored copy.

**Nothing here rests on `python3-yaml` either way**, which is the only part
wrench needs settled, and it is settled by the paragraph above rather than by
what that package turns out to be.

FACT 2026-08-26, measured here: it is installed at 6.0.2-1+b2 and **not manually
installed**, so apt holds it only through a dependency edge.
`apt-mark showmanual` matches neither it nor `python3-jsonschema`, and the latter
is not installed at all.

**Answered 2026-08-28: artefact, not floor.** The declaration was undeclared at
dotfiles `bf38481`, and the package stays installed.

Neither of the two readings this file used to carry was right, and the true one
is narrower than both: **the package is llvm's, and only the DECLARATION was ever
dotfiles'.** It arrived as `llvm-19-tools`' dependency, and the line declaring it
invented a reason — its comment said the system `python3` needs a parser before
tooling exists, which was never true of anything in that repository.

Verified here rather than taken, 2026-08-28:

    dotfiles bf38481                    resolves, subject matches
    packages.toml                       no longer declares it; a comment says
                                        deliberately not
    apt-mark showmanual                 does not list it
    dpkg -s python3-yaml                install ok installed

So it is undeclared and still present, which is correct: `llvm` is declared, and
removing the package would take `llvm-19-dev` and `llvm-19-tools` with it.

**The retracted readings are recorded because the retraction is the lesson.**
dotfiles first called it an orphan swept up in a cleanup, withdrew that when our
user mentioned a QEMU install test, and marked it unverified. The QEMU run was
real and left no record — and was not what put the package there. A true detail
arriving mid-investigation moved the reading toward a wrong answer, which is
worth more than the answer itself.

**Nothing wrench holds ever rested on it**, which was the only part wrench needed
settled, and it was settled by the paragraph above this rather than by what the
package turned out to be.

**Whether `jsonschema` is imported lazily is now wrench's own call**, on wrench's
merits, with no external constraint. The reason to keep it at module level is
that the pack validates and validation is the point; a lazy import would trade a
clear failure at import for an obscure one at first use, and buy nothing now that
no caller lacks the module.

## What is still owed, and it is dotfiles'

A machine rebuilt from `bin/setup` gets every tool and no wrench, because the
`python_projects` list does not exist, re-measured 2026-08-28: nothing under
`dotfiles/bin/` mentions wrench.
`clank/inbox/dotfiles/declare-wrench-and-its-bootstrap-dependency/`, now deleted
as a resolved entry is, was promoted to a dotfiles task rather than resolved
inline: it needs the manifest
list, `bin/setup` emitting `-e <path>` into the generated `requirements.in`, and a
`converge` step so an undeclared editable install is visible.

Until that lands, the editable install is done by hand and `docs/PROJECT.md`
carries the command.
