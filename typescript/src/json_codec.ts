/**
 * The JSON codec: bytes to a structure, and a structure to canonical bytes.
 *
 * Canonical form is two-space indent, one key to a line, keys sorted, and a
 * trailing newline (FR-4.6). It is `deno fmt` clean, which is deliberate,
 * because the gate already runs `deno fmt --check` over `schemas/*.json` and a
 * second answer about JSON layout would put two formatters in one repository.
 *
 * THE RUNTIME EMITS AND THIS ADDS TWO ADAPTERS. `JSON.stringify` is already
 * canonical form for everything but ordering and floats, which is why JSON
 * needed no hand-written emitter in any pack. Both adapters are supported hooks
 * rather than text this file writes:
 *
 *   sort the keys       a replacer ARRAY names the properties and their order,
 *                       so one sorted list of every key in the tree orders
 *                       every mapping in it
 *   positional floats   FR-4.8, through `JSON.rawJSON`, which is the standard
 *                       way to hand the serialiser digits it must not respell
 *
 * THE ORDERING ADAPTER IS NOT OPTIONAL AND NOT COSMETIC. An object's own
 * property order is not insertion order: an integer-like key is enumerated
 * first, in ascending numeric order, whatever order it was written in. So
 * rebuilding an object with its keys inserted sorted produces `2` before `10`,
 * where every other pack sorts as strings and writes `10` before `2`. Measured
 * against the parity tree's `keys_needing_order`.
 */

import { EncodeError, ParseError } from "./errors.ts";
import { canonicalNumberText } from "./float_text.ts";
import { asText, type Codec, type WrenchValue } from "./seams.ts";

/** `JSON.rawJSON`, which is standard and not yet in every type definition. */
const rawJSON = (JSON as unknown as {
  rawJSON(text: string): unknown;
}).rawJSON;

export class JSONCodec implements Codec {
  /**
   * Bytes into maps, lists and scalars.
   *
   * A `SyntaxError` from the parser does not cross this boundary; the cause is
   * kept, so a consumer catches one family rather than knowing which parser
   * wrench binds.
   *
   * NEGATIVE ZERO IS A VALUE IN JSON AND NOT A SPELLING OF ZERO. JavaScript is
   * the reference for what a JSON document means and V8 reads `-0` as a signed
   * zero, which is what FR-4.11 records. Nothing here has to arrange that: it
   * is what the runtime already does, and this pack is the one where that
   * behaviour is native rather than reproduced.
   */
  decode(data: Uint8Array | string): WrenchValue {
    try {
      return JSON.parse(asText(data)) as WrenchValue;
    } catch (cause) {
      throw new ParseError("could not parse the JSON", { cause });
    }
  }

  /** A structure into canonical bytes. */
  encode(value: WrenchValue): Uint8Array {
    try {
      const prepared = withRawNumbers(value);
      const order = [...collectKeys(value, new Set<string>())].sort();
      return new TextEncoder().encode(
        `${JSON.stringify(prepared, order, INDENT)}\n`,
      );
    } catch (cause) {
      throw new EncodeError("could not write canonical JSON", { cause });
    }
  }
}

const INDENT = 2;

/**
 * Every key anywhere in the tree, which becomes the replacer array.
 *
 * Sorted once and applied at every level, because the array's order is the
 * order each mapping's properties come out in, and one string sort is the same
 * answer at every depth.
 */
function collectKeys(value: unknown, into: Set<string>): Set<string> {
  if (Array.isArray(value)) {
    for (const item of value) collectKeys(item, into);
    return into;
  }
  if (value !== null && typeof value === "object") {
    const record = value as Record<string, unknown>;
    for (const key of Object.keys(record)) {
      into.add(key);
      collectKeys(record[key], into);
    }
  }
  return into;
}

/**
 * The float adapter, applied to the structure before the serialiser sees it.
 *
 * A number becomes a raw JSON fragment carrying FR-4.8's spelling, so
 * `JSON.stringify` writes those digits and respells nothing. Everything else,
 * string escaping included, is the runtime's and is the part every pack found
 * correct.
 *
 * A value with no canonical form is refused here rather than emitted, because
 * `JSON.stringify` writes `null` for a NaN and for an infinity, which is a
 * different document rather than a failure.
 */
function withRawNumbers(value: unknown): unknown {
  if (typeof value === "number") return rawJSON(canonicalNumberText(value));
  if (Array.isArray(value)) return value.map(withRawNumbers);
  if (
    value === null || typeof value === "boolean" || typeof value === "string"
  ) {
    return value;
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(record)) {
      out[key] = withRawNumbers(record[key]);
    }
    return out;
  }
  throw new TypeError(`cannot write ${typeof value} in canonical form`);
}

/** The codec, named rather than inferred from a filename. */
export const JSON_CODEC: JSONCodec = new JSONCodec();
