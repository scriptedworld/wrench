# FR-3.10a

| ID | Requirement | |
|---|---|---|
| FR-3.10a | A `$ref` reaches one of three tiers and no other. Within the document, `#/$defs/…` and `#anchor` resolve and constrain. The shipped set resolves by the `$id` each schema declares. Everything else is refused. The middle tier is the one a consumer wants: an adapter extending the envelope references it rather than copying it, because a copy can drift and FR-3.2 rules that out. | [D] |
