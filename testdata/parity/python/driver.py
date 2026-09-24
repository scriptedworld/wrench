#!/usr/bin/env python3
"""The Python pack's parity driver: encode the shared tree, decode a file.

Called by `bin/test-cross-pack-parity.py`, which owns the wire format this
reads and writes. Two subcommands, the same two in every pack's driver:

    driver.py encode <yaml|json> <probe-in.json> <out-path>
    driver.py decode <yaml|json> <in-path> <probe-out.json>

It calls the pack's public API and nothing else. A driver that repaired,
rounded or reordered anything would hide the divergence the checker exists to
find, so every value outside wrench's model is passed through as a `foreign`
node for the checker to report rather than being coerced here.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from typing import Any

from wrench import (
    JSON,
    LOCAL_FILE,
    YAML,
    Codec,
    compile_schema,
    load_formatted_file,
    save_formatted_file,
)

WIRE = 1

# Anything is a valid instance, so the parity tree is judged by the codecs and
# not by a schema. The schema argument cannot be omitted (FR-2.2), so the
# permissive one is what a driver hands it.
ANY_SCHEMA = compile_schema("wrench-parity-driver", "{}")

CODECS: dict[str, Codec] = {"yaml": YAML, "json": JSON}


def to_probe(value: Any) -> dict[str, Any]:
    """Turn a decoded value into the checker's tagged wire form."""
    if value is None:
        return {"k": "null"}
    if isinstance(value, bool):
        return {"k": "bool", "v": "true" if value else "false"}
    if isinstance(value, int):
        return {"k": "int", "v": str(value)}
    if isinstance(value, float):
        return {"k": "float", "v": struct.pack(">d", value).hex()}
    if isinstance(value, str):
        return {"k": "str", "v": value.encode("utf-8").hex()}
    if isinstance(value, list):
        return {"k": "seq", "v": [to_probe(item) for item in value]}
    if isinstance(value, dict):
        return {"k": "map", "v": [_pair(k, v) for k, v in value.items()]}
    return {"k": "foreign", "v": f"{type(value).__name__}: {value!r}"}


def _pair(key: Any, value: Any) -> list[Any]:
    if not isinstance(key, str):
        return [f"?{type(key).__name__}:{key!r}".encode().hex(), to_probe(value)]
    return [key.encode("utf-8").hex(), to_probe(value)]


def from_probe(node: dict[str, Any]) -> Any:
    """Turn the checker's tagged wire form into a native value."""
    kind = node["k"]
    if kind == "null":
        return None
    if kind == "bool":
        return node["v"] == "true"
    if kind == "int":
        return int(node["v"])
    if kind == "float":
        return struct.unpack(">d", bytes.fromhex(node["v"]))[0]
    if kind == "str":
        return bytes.fromhex(node["v"]).decode("utf-8")
    if kind == "seq":
        return [from_probe(item) for item in node["v"]]
    if kind == "map":
        return {
            bytes.fromhex(key).decode("utf-8"): from_probe(item)
            for key, item in node["v"]
        }
    raise ValueError(f"unknown wire node kind {kind!r}")


def encode(fmt: str, probe_path: str, out_path: str) -> None:
    wire = json.loads(Path(probe_path).read_text(encoding="utf-8"))
    if wire["wire"] != WIRE:
        raise ValueError(f"wire version {wire['wire']} is not {WIRE}")
    save_formatted_file(
        from_probe(wire["value"]), out_path, ANY_SCHEMA, CODECS[fmt], LOCAL_FILE
    )


def decode(fmt: str, in_path: str, probe_path: str) -> None:
    value = load_formatted_file(in_path, ANY_SCHEMA, CODECS[fmt], LOCAL_FILE)
    Path(probe_path).write_text(
        json.dumps({"wire": WIRE, "value": to_probe(value)}), encoding="utf-8"
    )


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[0] not in ("encode", "decode") or argv[1] not in CODECS:
        print(
            f"usage: {sys.argv[0]} encode|decode yaml|json <in> <out>", file=sys.stderr
        )
        return 2
    action, fmt, source, target = argv
    if action == "encode":
        encode(fmt, source, target)
    else:
        decode(fmt, source, target)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
