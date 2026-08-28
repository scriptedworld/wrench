# FR-2.9

| ID | Requirement | |
|---|---|---|
| FR-2.9 | **What a decoder produces is maps, lists and JSON scalars, and nothing else.** A format with a type JSON does not have is reconciled at the decoder rather than left for everything downstream, because that shape is what makes one schema validate a file whichever codec read it, and what makes a codec interchangeable at all. A value with no JSON equivalent is coerced where the spelling is lossless and refused where it is not: a YAML timestamp becomes its ISO 8601 string, a mapping key that is not a string is refused. | [A/D] |
