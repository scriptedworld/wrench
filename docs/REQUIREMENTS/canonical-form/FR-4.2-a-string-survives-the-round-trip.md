# FR-4.2

| ID | Requirement | |
|---|---|---|
| FR-4.2 | `no`, `1.20` and `null` therefore survive a round trip as the strings they were, and a boolean stays a boolean. Quoting marks intent, so nothing downstream has to guess which was meant. **The complement is the surprising half:** an *unquoted* `1.20` was a number, and that number has no trailing zero, so it round-trips as `1.2`. That is the rule working rather than a defect, and it is the case somebody writing a version number unquoted meets once. FACT 2026-08-27, checked in all three packs. | [A] |
