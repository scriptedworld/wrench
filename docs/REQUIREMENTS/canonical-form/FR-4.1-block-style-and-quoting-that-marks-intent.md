# FR-4.1

| ID | Requirement | |
|---|---|---|
| FR-4.1 | YAML is emitted in canonical form: block style, one key to a line, and a scalar quoted exactly when it is meant to be a string, so its type is never in question. Booleans and numbers stay bare. A value with no canonical form is refused rather than guessed at. | [A go,python:edge,negative] |
