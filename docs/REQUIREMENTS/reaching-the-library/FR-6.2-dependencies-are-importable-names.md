# FR-6.2

| ID | Requirement | |
|---|---|---|
| FR-6.2 | The pack's dependencies are on names being importable in the environment it is installed into, not on a resolver having run there. It imports `yaml`, `jsonschema` and `referencing` by name, so a platform package and a pip install satisfy it identically. ~~Debian's `python3-yaml` through the one channel available before any other is~~ **restated 2026-08-26**: that framing rested on the bootstrap window, which does not consume this pack. | [A/D python] |
