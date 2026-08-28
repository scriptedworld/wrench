# FR-3.10

| ID | Requirement | |
|---|---|---|
| FR-3.10 | A schema handed to the compile call may reference a shipped schema by its `$id`, and **may reference nothing else**. A `$ref` outside the shipped set is refused rather than fetched over the network or read from disk, so what a schema means depends on nothing beyond the process and the one shipped copy. A caller may not redefine a shipped `$id`, because a document deciding what the envelope schema means is the one thing a shipped schema exists to fix. `WRENCH_ALLOW_EXTERNAL_SCHEMA_REFS=1` restores the underlying implementation's behaviour, and is on borrowed time: the Python binding already calls that behaviour a security vulnerability and is removing it. | [A/D] |
