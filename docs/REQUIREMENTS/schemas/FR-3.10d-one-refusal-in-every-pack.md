# FR-3.10d

| ID | Requirement | |
|---|---|---|
| FR-3.10d | A refused reference produces the same `schema` failure in every pack, carrying one sentence: `cannot resolve <resolved reference>: a schema may reference the shipped schemas and its own fragments, and nothing else`. The three packs refuse by three mechanisms — a loader, a registry holding only the shipped set, and a retriever — and a consumer reading the failure cannot tell which language produced it. The bound library's own wording never crosses the boundary, per FR-2.11. | [D] |
