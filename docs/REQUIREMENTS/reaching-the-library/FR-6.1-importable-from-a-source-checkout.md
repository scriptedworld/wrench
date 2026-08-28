# FR-6.1

| ID | Requirement | |
|---|---|---|
| FR-6.1 | The Python pack is importable from a source checkout, with no install having run. Its own suite runs that way, on `PYTHONPATH`, and the pack reads `schemas/` from the repository rather than from package data, which is why an editable install is the only supported form. ~~`dotfiles/bin/setup` runs on `/usr/bin/python3` before mise exists~~ **restated 2026-08-26**: that was the original motivation and it was disproven. Nothing in the bootstrap window imports wrench, and nothing is planned to. See `docs/DECISIONS/the-pack-is-installed-after-mise-not-before.md`. | [A/D python] |
