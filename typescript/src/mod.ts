/**
 * wrench reads, writes and validates the form of the ecosystem's structured
 * files. This is the TypeScript pack.
 *
 * THE TWO CALLS ARE THE WHOLE OF FILE HANDLING (FR-2.1):
 *
 *     loadFormattedFile(path, schema, codec, reader) -> value
 *     saveFormattedFile(value, path, schema, codec, writer)
 *
 * The contract names them `load_formatted_file` and `save_formatted_file`, and
 * this pack spells them the way TypeScript spells a function, which is what
 * `each-pack-spells-the-calls-its-own-way` decides. The argument order and
 * meaning are the contract and are not TypeScript's to change.
 *
 * Load reads, decodes, then validates. Save validates, encodes, then writes.
 * Validating on the way out is not symmetry for its own sake: it stops a caller
 * writing a structure wrench would refuse to read back (FR-2.4), so a file
 * produced by a save always survives a load.
 *
 * The schema argument cannot be omitted (FR-2.2). It can be wrong, and no part
 * of this library detects that (FR-2.3).
 *
 * TWO CODECS SHIP, YAML AND JSON. TOML was the third and is retired (FR-2.7):
 * no maintained library in any of the languages could emit its canonical form,
 * and the hand-written emitters written instead wrote documents they could not
 * read back.
 */

import { UsageError, WrenchError } from "./errors.ts";
import { JSON_CODEC } from "./json_codec.ts";
import type { Codec, Reader, Schema, WrenchValue, Writer } from "./seams.ts";
import { YAML_CODEC } from "./yaml_codec.ts";

export * from "./errors.ts";
export type { Codec, Reader, Schema, WrenchValue, Writer } from "./seams.ts";
export { LOCAL_FILE, LocalFile } from "./local_file.ts";
export { canonicalFloatText, canonicalNumberText } from "./float_text.ts";
export {
  CompiledSchema,
  compileSchema,
  type SchemaDocument,
  schemas,
  shippedIds,
  unresolved,
} from "./schema.ts";
export { JSONCodec } from "./json_codec.ts";
export { YAMLCodec } from "./yaml_codec.ts";

/**
 * The codecs, named rather than inferred from a filename.
 *
 * Choosing a parser by suffix would make behaviour depend on what a file is
 * called, and renaming a file would silently change how it is read. That is the
 * implicitness FR-2.2 exists to remove.
 *
 * Re-exported under their short names rather than assigned, because a module
 * binding called `JSON` would shadow the global one everything here uses.
 */
export { YAML_CODEC as YAML } from "./yaml_codec.ts";
export { JSON_CODEC as JSON } from "./json_codec.ts";

/**
 * Read `path` through `reader`, decode it with `codec`, validate the result.
 *
 * Each step's failure is its own kind, so a caller learns whether the file was
 * unreadable, unparseable or simply wrong. A codec is handed bytes and a schema
 * a structure, so neither knows which file it is working on: both throw with no
 * path and this fills it in.
 */
export function loadFormattedFile(
  path: string,
  schema: Schema,
  codec: Codec,
  reader: Reader,
): WrenchValue {
  requireSeams(path, schema, codec, reader, "reader");
  const bytes = reader.read(path);
  const value = withPath(path, () => codec.decode(bytes));
  withPath(path, () => schema.validate(value));
  return value;
}

/**
 * Validate `value`, encode it with `codec`, and put it in place through
 * `writer`.
 */
export function saveFormattedFile(
  value: WrenchValue,
  path: string,
  schema: Schema,
  codec: Codec,
  writer: Writer,
): void {
  requireSeams(path, schema, codec, writer, "writer");
  withPath(path, () => schema.validate(value));
  const bytes = withPath(path, () => codec.encode(value));
  writer.write(path, bytes);
}

/** The wrappers, which supply the codec and add nothing else (FR-2.10). */

export function loadYamlFile(
  path: string,
  schema: Schema,
  reader: Reader,
): WrenchValue {
  return loadFormattedFile(path, schema, YAML_CODEC, reader);
}

export function saveYamlFile(
  value: WrenchValue,
  path: string,
  schema: Schema,
  writer: Writer,
): void {
  saveFormattedFile(value, path, schema, YAML_CODEC, writer);
}

export function loadJsonFile(
  path: string,
  schema: Schema,
  reader: Reader,
): WrenchValue {
  return loadFormattedFile(path, schema, JSON_CODEC, reader);
}

export function saveJsonFile(
  value: WrenchValue,
  path: string,
  schema: Schema,
  writer: Writer,
): void {
  saveFormattedFile(value, path, schema, JSON_CODEC, writer);
}

/**
 * A missing seam is `usage`, the kind that names no step that ran, because the
 * call was made wrongly before any file was touched.
 *
 * TypeScript's types say all of this, and are erased at run time, so a
 * JavaScript caller and a caller with an `any` in the way both reach here. Rust
 * omits the kind because the same call does not compile there; TypeScript
 * cannot, because it compiles and then runs anyway.
 */
function requireSeams(
  path: unknown,
  schema: unknown,
  codec: unknown,
  io: unknown,
  side: "reader" | "writer",
): void {
  if (typeof path !== "string" || path === "") {
    throw new UsageError("no path was given");
  }
  if (!hasMethod(schema, "validate")) {
    throw new UsageError("no schema was given");
  }
  if (!hasMethod(codec, "decode") || !hasMethod(codec, "encode")) {
    throw new UsageError("no codec was given");
  }
  if (!hasMethod(io, side === "reader" ? "read" : "write")) {
    throw new UsageError(`no ${side} was given`);
  }
}

function hasMethod(subject: unknown, name: string): boolean {
  return subject !== null &&
    (typeof subject === "object" || typeof subject === "function") &&
    typeof (subject as Record<string, unknown>)[name] === "function";
}

/** Attach the file to an error thrown by something that does not know it. */
function withPath<T>(path: string, step: () => T): T {
  try {
    return step();
  } catch (error) {
    if (error instanceof WrenchError) throw error.withPath(path);
    throw error;
  }
}
