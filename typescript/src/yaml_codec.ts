/**
 * The YAML codec: bytes to a structure, and a structure to canonical bytes.
 *
 * THE LIBRARY EMITS AND THIS ADDS FOUR ADAPTERS. Nothing here writes a
 * character of YAML: layout, indentation, escaping and line breaks are all
 * js-yaml's, and its escape table is the one that ships. The adapters exist
 * because they preserve MEANING rather than layout, which is what
 * `packs-agree-on-structure-not-on-bytes` holds every pack to:
 *
 *   sort the keys                two runs over one structure must agree
 *   quote every string and key   `no`, `1.20`, `null` and `10` stay what they
 *                                were. The key is the sharp one: to a YAML 1.1
 *                                reader an unquoted `10:` is an integer key
 *   positional floats            FR-4.8, and `1e+20` read by a naive numeric
 *                                pattern yields 1
 *   null written as the word     an empty value and a missing one should not
 *                                look the same to a reader
 *
 * WHICH LIBRARY, AND WHY IT IS NOT THE OTHER ONE. Both maintained TypeScript
 * YAML libraries survive the acceptance check, which is a round trip of the
 * control-character fixture through the library's own reader. `yaml` 2.9.0 then
 * fails the requirement the check is a proxy for: its double-quoted escaping is
 * driven by `JSON.stringify`, which escapes nothing above U+001F, so U+007F,
 * U+0085, U+00A0, U+2028, U+2029 and U+FEFF are written RAW. Its own reader
 * takes them back, and Python's does not: ruamel refuses the whole document
 * with `unacceptable character #x007f`. A file no sibling pack can read is not
 * structural parity, so the round trip through one library is necessary and not
 * sufficient. Measured 2026-09-08.
 *
 * js-yaml escapes them as libyaml does, `\x7F`, `\N`, `\_`, `\L`, `\P` and
 * `U+FEFF`, and leaves U+200B alone, which is a printable character and is what
 * every other pack does with it.
 *
 * `forceQuotes` IS NOT THE QUOTING ADAPTER, and looks like it. It skips keys by
 * construction, and it quotes numbers and booleans as well as strings, which
 * makes the emitter write `!!int '3'` to keep the type. The hooks that do the
 * job are the schema's tag list and `transform`, which hands the emitter's own
 * AST over before it is rendered.
 */

import {
  CORE_SCHEMA,
  dump,
  floatCoreTag,
  intCoreTag,
  load,
  mapTag,
  nullCoreTag,
  realMapTag,
  SCALAR_STYLE,
  Schema,
  visit,
} from "js-yaml";

import { EncodeError, ParseError } from "./errors.ts";
import { canonicalNumberText } from "./float_text.ts";
import { asText, type Codec, type WrenchValue } from "./seams.ts";

const STR_TAG = "tag:yaml.org,2002:str";

/**
 * Which numbers are written without a decimal point.
 *
 * The same predicate decides the spelling and selects the tag, and that is what
 * keeps the emitter from writing an explicit `!!int`: a value the spelling
 * gives a `.0` must be selected by the float tag, or the text and the tag
 * disagree and the library says so in the output.
 *
 * JavaScript has one number type, so this is a property of the value rather
 * than of a type it was decoded as. Past 2^53 it is also the widening FR-4.10
 * asks for: a literal that arrived already rounded is written with a `.0`
 * rather than as an exact-looking integer it is not.
 */
function isPlainInteger(value: unknown): boolean {
  return typeof value === "number" && Number.isSafeInteger(value) &&
    !Object.is(value, -0);
}

// Adapters three and four. The CORE tags with `represent` replaced, so the
// reading side stays the library's except where the contract differs from it.
// deno-lint-ignore no-explicit-any
const INT_OUT: any = {
  ...intCoreTag,
  identify: isPlainInteger,
  represent: canonicalNumberText,
  // FR-4.11's YAML half. `Number("-0")` is a negative zero and an integer zero
  // cannot carry the sign, so the reader's answer is normalised here. Only the
  // float tag keeps a sign, and only for a source with a decimal point.
  resolve: (source: string, isExplicit: boolean, tagName: string) => {
    const value = intCoreTag.resolve(source, isExplicit, tagName);
    return Object.is(value, -0) ? 0 : value;
  },
};

/**
 * FR-4.11: in YAML `-0` is the integer zero and only `-0.0` carries a sign,
 * because YAML's type repository gives `0|-?[1-9][0-9]*` as the canonical
 * integer and zero has no signed variant there. The int tag already answers the
 * first half. js-yaml normalises the second to a positive zero, so this puts
 * the sign back, which is what makes a negative zero survive the round trip.
 */
// deno-lint-ignore no-explicit-any
const FLOAT_OUT: any = {
  ...floatCoreTag,
  identify: (data: unknown) => typeof data === "number",
  represent: canonicalNumberText,
  resolve: (source: string, isExplicit: boolean, tagName: string) => {
    const value = floatCoreTag.resolve(source, isExplicit, tagName);
    const signed = source.trimStart().startsWith("-") && /[.eE]/.test(source);
    return value === 0 && signed ? -0 : value;
  },
};

// deno-lint-ignore no-explicit-any
const NULL_OUT: any = { ...nullCoreTag, represent: () => "null" };

// deno-lint-ignore no-explicit-any
function replaced(tags: readonly any[]): any[] {
  return tags.map((tag) => {
    if (tag.tagName === intCoreTag.tagName) return INT_OUT;
    if (tag.tagName === floatCoreTag.tagName) return FLOAT_OUT;
    if (tag.tagName === nullCoreTag.tagName) return NULL_OUT;
    return tag;
  });
}

/** What the emitter is given. */
const WRITE_SCHEMA = new Schema(replaced(CORE_SCHEMA.tags));

/**
 * What the reader is given, and it differs in one tag.
 *
 * `realMapTag` builds a native `Map`, so a mapping key keeps the type it was
 * written with. The object-based tag turns `1:` into the key `"1"`, and a
 * coercion that is not reversible has to be refused rather than made (FR-2.9).
 * There is nowhere else to see it: by the time a mapping is a JavaScript object
 * the evidence is gone.
 */
const READ_SCHEMA = new Schema(
  replaced(CORE_SCHEMA.tags).map((
    tag,
  ) => (tag.tagName === mapTag.tagName ? realMapTag : tag)),
);

/**
 * Adapters one and two, through the emitter's own AST.
 *
 * A scalar carries its resolved tag, so the string ones are told to print
 * double-quoted and a number is left alone by construction rather than by
 * inspecting its text.
 *
 * The keys are sorted by their spelling, which is the same string comparison
 * every pack makes and is what puts `10` before `2`.
 */
// deno-lint-ignore no-explicit-any
function adapt(documents: any[]): void {
  // deno-lint-ignore no-explicit-any
  visit(documents, (node: any) => {
    if (node.kind === "scalar" && node.tag === STR_TAG) {
      node.style = SCALAR_STYLE.DOUBLE_QUOTED;
    }
    if (node.kind !== "mapping") return;
    // deno-lint-ignore no-explicit-any
    node.items.sort((one: any, two: any) => {
      const first = one.key.kind === "scalar" ? one.key.value : "";
      const second = two.key.kind === "scalar" ? two.key.value : "";
      return first < second ? -1 : first > second ? 1 : 0;
    });
  });
}

/**
 * `noRefs` is load-bearing. Left off, a structure holding the same object twice
 * is emitted with an anchor and an alias, which is a file this codec's own
 * reader then refuses. `flowLevel: -1` keeps block style at every depth
 * (FR-4.4), and `lineWidth: -1` turns folding off, because a folded scalar is a
 * line break inserted into a value.
 */
const WRITE_OPTIONS = {
  schema: WRITE_SCHEMA,
  flowLevel: -1,
  lineWidth: -1,
  noCompatMode: false,
  noRefs: true,
  skipInvalid: false,
  transform: adapt,
};

/**
 * `maxAliases: 0` refuses aliases rather than expanding them: a document that
 * expands to something larger than itself is a denial of service in a library
 * whose whole job is reading files from elsewhere. `json: false` keeps a
 * duplicate key an error rather than letting the last one win.
 */
const READ_OPTIONS = { schema: READ_SCHEMA, json: false, maxAliases: 0 };

export class YAMLCodec implements Codec {
  /**
   * Bytes into maps, lists and scalars.
   *
   * A `YAMLException` does not cross this boundary; the cause is kept.
   *
   * An empty document is `null` rather than a parse failure, which is what the
   * Python pack answers and what a caller reading a file somebody has emptied
   * expects. js-yaml calls it an error, so this is the one place the library's
   * reading is overridden rather than passed on.
   */
  decode(data: Uint8Array | string): WrenchValue {
    const text = asText(data);
    if (text.trim() === "") return null;
    try {
      return fromMaps(load(text, READ_OPTIONS));
    } catch (cause) {
      throw new ParseError(
        `could not parse the YAML: ${(cause as Error).message.split("\n")[0]}`,
        {
          cause,
        },
      );
    }
  }

  /** A structure into canonical bytes. */
  encode(value: WrenchValue): Uint8Array {
    try {
      refuseValuesWithNoCanonicalForm(value);
      return new TextEncoder().encode(dump(value, WRITE_OPTIONS));
    } catch (cause) {
      throw new EncodeError(
        `could not write canonical YAML: ${
          (cause as Error).message.split("\n")[0]
        }`,
        { cause },
      );
    }
  }
}

/**
 * The reader's `Map`s as plain objects, refusing a key that is not a string.
 *
 * An unquoted `10:` is a number to the reader and a quoted `"10":` is a string,
 * and the two are the same key by the time the document is a JavaScript object.
 * Refusing here is what stops a file meaning one thing on disk and another in
 * the structure a schema then validates.
 */
function fromMaps(value: unknown): WrenchValue {
  if (value instanceof Map) {
    const out: Record<string, WrenchValue> = {};
    for (const [key, item] of value) {
      if (typeof key !== "string") {
        throw new TypeError(`mapping key ${describe(key)} is not a string`);
      }
      out[key] = fromMaps(item);
    }
    return out;
  }
  if (Array.isArray(value)) return value.map(fromMaps);
  if (value === undefined) return null;
  return value as WrenchValue;
}

/** A refused key, named in a way a reader can find in the file. */
function describe(key: unknown): string {
  if (key === null) return "null";
  if (typeof key === "object") {
    return Array.isArray(key) ? "a sequence" : "a mapping";
  }
  return JSON.stringify(String(key));
}

/**
 * A value with no canonical form is refused rather than guessed at (FR-4.1).
 *
 * A JavaScript object can only have string keys, so what this reaches is the
 * value a caller could not write at all: an `undefined`, a function, a symbol,
 * a bigint, and a NaN or an infinity, which the emitter would otherwise spell
 * as `.nan` and `.inf` where JSON Schema has no way to represent either.
 */
function refuseValuesWithNoCanonicalForm(value: unknown): void {
  if (
    value === null || typeof value === "boolean" || typeof value === "string"
  ) return;
  if (typeof value === "number") {
    canonicalNumberText(value);
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) refuseValuesWithNoCanonicalForm(item);
    return;
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    for (const key of Object.keys(record)) {
      refuseValuesWithNoCanonicalForm(record[key]);
    }
    return;
  }
  throw new TypeError(`cannot write ${typeof value} in canonical form`);
}

/** The codec, named rather than inferred from a filename. */
export const YAML_CODEC: YAMLCodec = new YAMLCodec();
