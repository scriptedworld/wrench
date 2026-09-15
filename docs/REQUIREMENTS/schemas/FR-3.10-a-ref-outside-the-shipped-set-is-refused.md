# FR-3.10

| ID | Requirement | |
|---|---|---|
| FR-3.10 | A schema handed to the compile call may reference a shipped schema by its `$id`, and **may reference nothing else**. A `$ref` outside the shipped set is refused rather than fetched over the network or read from disk, so what a schema means depends on nothing beyond the process and the one shipped copy. There is no way to ask for more: no argument, no environment variable, no build configuration. A caller may not redefine a shipped `$id`, because a shipped schema is there to fix what the envelope schema means, and a document may not decide it. | [A/D] |
