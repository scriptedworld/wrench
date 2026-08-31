# The Python pack is installed after mise, not before it

Answers FR-7.4, which asked how the pack reaches its bootstrap consumer. It has
no bootstrap consumer, so the question dissolved rather than being decided.

## The premise that failed

FR-6.1 and FR-6.2 were written on the belief that `dotfiles/bin/setup` runs on
`/usr/bin/python3` before mise, uv or pip exist, and would want to read a
manifest through this pack. A pack needing `pip install` first would have meant
installing requires the installer, so it was shaped to import by name and
survive on whatever apt supplied.

Nothing in that window consumes wrench, measured against the consuming
repository at `6d00d2d`:

- Nothing in `bin/` imports `yaml` at any level, lazy or otherwise.
  `grep -rnE 'import yaml|yaml\.safe_load|yaml\.load' bin/` returns nothing.
- The manifests are TOML and `bin/_pkg.py` reads them with stdlib `tomllib`,
  which is the stated reason they are TOML: the tool that installs everything
  must not itself need something installed first.
- The only YAML there is `bolt.*.yaml`, read by a Go binary. No Python touches
  it.

So the bootstrap window needs no YAML, no validation, and nothing from wrench.

## Where it is installed instead

Into the standard mise-managed Python through a `python_projects` list, or via
`uv tool` if it ever becomes a tool rather than a module to import. Both land
after mise exists.

That list does not exist yet, so this is intent relayed at one remove rather
than something measured. `python_projects` has never appeared in
`packages.toml`, on any branch, in any commit.

## What it changes here

**FR-6.1 and FR-6.2 keep their property and lose their justification.** Importing
by name and running from a source checkout are still true and still wanted, for
reasons of their own rather than because an interpreter without pip has to cope.

The editable install this once required is gone with the same premise. The pack
carries the shipped schemas as generated source, so it resolves them without
reference to where it sits and every install form works.
`every-pack-compiles-the-schemas-in` has that.

**Nothing gets declared or vendored on dotfiles' account.** Not `python3-yaml`,
not `python3-jsonschema`, and no vendored copy.

**Nothing wrench holds ever rested on `python3-yaml`**, which is the only part
wrench needed settled, and it is settled by the route above rather than by what
that package turns out to be. It is an artefact rather than a floor: it arrived
as a dependency of `llvm-19-tools`, the line declaring it in dotfiles invented a
reason, and that declaration is gone at dotfiles `bf38481` while the package
stays installed. Removing it would take `llvm-19-dev` and `llvm-19-tools` with
it.

**Whether `jsonschema` is imported lazily is wrench's own call**, on wrench's
merits, with no external constraint. The reason to keep it at module level is
that the pack validates and validation is the point; a lazy import would trade a
clear failure at import for an obscure one at first use, and buy nothing now
that no caller lacks the module.

## What is still owed, and it is dotfiles'

A machine rebuilt from `bin/setup` gets every tool and no wrench, because the
`python_projects` list does not exist and nothing under `dotfiles/bin/` mentions
wrench. That was promoted to a dotfiles task: it needs the manifest list,
`bin/setup` emitting `-e <path>` into the generated `requirements.in`, and a
`converge` step so an undeclared editable install is visible.

Until it lands, wrench is installed by hand. Any form works.
