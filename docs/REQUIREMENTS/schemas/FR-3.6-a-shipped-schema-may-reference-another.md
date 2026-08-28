# FR-3.6

| ID | Requirement | |
|---|---|---|
| FR-3.6 | A shipped schema may reference another by the `$id` it declares, and the reference resolves from the shipped set alone without reaching the network. A shape two schemas both need is then written once rather than copied into each, because two copies are free to drift and nothing would report it. | [D] |
