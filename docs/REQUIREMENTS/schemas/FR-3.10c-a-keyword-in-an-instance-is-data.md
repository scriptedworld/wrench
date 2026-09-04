# FR-3.10c

| ID | Requirement | |
|---|---|---|
| FR-3.10c | `$ref`, `$id` and `$schema` are keywords in a schema and ordinary keys in the document being validated. Nothing interprets them in an instance: a data file carrying `$ref` pointed at a file that exists is accepted and that file is not read. Validation applies the schema to the document; it never reads the document as one. This holds for a document that is itself a schema, which is the case where the two roles are easiest to confuse. | [D] |
