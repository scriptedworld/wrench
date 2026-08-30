---
name: The packs disagree
about: Two packs produce different bytes, or accept different documents
---

wrench exists to make this impossible, so a report of it is the most useful kind
there is.

The value or document that shows it, small enough to paste.

What each pack produced. Bytes, not a description of the bytes, because the
difference is often whitespace or a spelling:

    Go
    Python
    Rust

Which packs you ran, and how. Version or commit if you have it.

Whether either output round trips through its own pack. A pack that reads back
its own output correctly and differs from its sibling is a different defect from
one that does not.

If the disagreement is a number or a control character, say the exact value. The
last two found here were a float spelling and a raw control character, and both
looked like nothing until the bytes were compared.
