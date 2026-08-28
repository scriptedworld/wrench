# FR-4.6

| ID | Requirement | |
|---|---|---|
| FR-4.6 | JSON's canonical form is two-space indent, one key to a line, keys sorted, and a trailing newline. It is `deno fmt` clean, which is not a coincidence: the gate already runs `deno fmt --check` over `schemas/*.json`, so a second answer about JSON layout would put two formatters in one repository. The match is one direction only, because `deno fmt` does not sort keys and collapses a short object onto one line, so it is a formatter rather than a canonical form. | [A/D] |
