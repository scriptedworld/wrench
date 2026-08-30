# FR-4.11

| ID | Requirement | |
|---|---|---|
| FR-4.11 | In JSON, `-0` decodes to a negative zero float in every pack, because JavaScript is the reference for what a JSON document means and V8 reads it as a signed zero. In YAML and TOML, `-0` decodes to the integer zero and only `-0.0` carries a sign. Both say so. TOML states that `-0` and `+0` are identical to an unprefixed zero while `-0.0` and `+0.0` map according to IEEE 754. YAML's type repository resolves an integer by `[-+]?(0|[1-9][0-9_]*)`, which `-0` matches, and gives the canonical form as `0|-?[1-9][0-9]*`, in which zero has no signed variant. So `-0` is the one literal with no decimal point whose type depends on the format it was written in. | [A/D] |
