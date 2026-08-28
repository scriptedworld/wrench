# FR-3.9

| ID | Requirement | |
|---|---|---|
| FR-3.9 | A document may declare the version of its format, as a semver string at the top level, and the field is optional. Absent means the document claims nothing, which is every document written before the field existed, so adding it broke none of them. Present, a consumer can refuse a major it does not understand rather than failing later on a field it cannot find. The definitions format does not carry it, being an open mapping where reserving a key costs a placeholder name. | [A] |
