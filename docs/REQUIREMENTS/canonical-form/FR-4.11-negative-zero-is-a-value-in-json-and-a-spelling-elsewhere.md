# FR-4.11

| ID | Requirement | |
|---|---|---|
| FR-4.11 | In JSON, `-0` decodes to a negative zero float in every pack, because JavaScript is the reference for what a JSON document means and V8 reads it as a signed zero. In YAML and TOML, `-0` decodes to the integer zero and only `-0.0` carries a sign. TOML states this outright, that `-0` and `+0` are identical to an unprefixed zero while `-0.0` and `+0.0` map according to IEEE 754; YAML has no such sentence and four independent implementations agree on the same answer. So `-0` is the one literal with no decimal point whose type depends on the format it was written in. | [A/D] |
