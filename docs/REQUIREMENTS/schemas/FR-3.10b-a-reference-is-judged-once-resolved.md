# FR-3.10b

| ID | Requirement | |
|---|---|---|
| FR-3.10b | Which tier a `$ref` belongs to is decided by the **resolved** reference and never by the text as written, because the same text is a different reference in a different document. A relative reference resolves against the document's `$id`; where a document declares none, the name the compile call was given is the base instead, and the `$id` wins wherever both are present. A refusal names the resolved reference, so a reader is not sent looking for a string that resolved to something else. | [D] |
