# FR-2.10

| ID | Requirement | |
|---|---|---|
| FR-2.10 | A wrapper per format supplies the codec and adds nothing else: `load_json_file`, `save_json_file` and the same pair for YAML and TOML. Validation stays in the core call, so the seam is unchanged in both directions. The codec is named rather than inferred from the file's suffix, because choosing a parser by filename would make behaviour depend on what a file is called and renaming one would silently change how it is read, which is the implicitness FR-2.2 exists to remove. | [A/D] |
