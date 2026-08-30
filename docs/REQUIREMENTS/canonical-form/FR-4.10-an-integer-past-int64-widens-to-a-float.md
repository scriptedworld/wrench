# FR-4.10

| ID | Requirement | |
|---|---|---|
| FR-4.10 | In YAML and JSON, an integer outside the signed 64-bit range decodes to a float in every pack, and the widening is visible in the spelling: `18446744073709551615` reads back as `18446744073709552000.0` rather than as a different exact integer. Within the range the value is exact and stays an integer. **TOML is excluded and refuses instead**, which is FR-4.7, because its own specification requires an error for an integer it cannot carry losslessly where YAML and JSON leave the range open. | [D] |
