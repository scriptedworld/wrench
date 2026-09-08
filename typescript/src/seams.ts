/**
 * The four seams, and the value model they pass between them.
 *
 * Each argument of the two calls is one job, so a format can be added without
 * inventing a source and a source without inventing a format (FR-2.5).
 *
 *   Codec   decode(bytes) -> value, encode(value) -> bytes
 *           The format. Knows nothing about where bytes came from.
 *           `encode` emits canonical form.
 *   Reader  read(path) -> bytes
 *           The IO on the way in. HANDED THE PATH, NOT THE BYTES.
 *   Writer  write(path, bytes)
 *           The IO on the way out. Puts the whole contents in place.
 *   Schema  validate(value)
 *           Applies to the decoded structure, not the text.
 *
 * A READER IS HANDED THE PATH RATHER THAN BYTES (FR-2.5a). Handing it bytes
 * would put the open where the caller is, and a test substituting a reader
 * would then be replacing the parse alone. Handed the path, a substituted
 * reader exercises every validation path against no filesystem at all.
 *
 * They are declared as interfaces because TypeScript has them and a consumer
 * gets the check for free. Nothing here asks for a class: any object with the
 * method is the seam, which is what lets a test supply four lines instead of an
 * implementation.
 */

/**
 * What a decoder produces and an encoder accepts, and nothing else (FR-2.9).
 *
 * Maps, lists and the JSON scalars. A format with a type JSON does not have is
 * reconciled in the decoder: a lossless spelling is coerced, and a mapping key
 * that is not a string is refused rather than stringified, because that
 * coercion is not reversible.
 *
 * JavaScript's `number` is the JSON number, so this pack needs no rule for
 * telling an integer from a float in the value model. What that costs is stated
 * in `float_text.ts`.
 */
export type WrenchValue =
  | null
  | boolean
  | number
  | string
  | WrenchValue[]
  | { [key: string]: WrenchValue };

/** The format. Bytes to a structure, and a structure to canonical bytes. */
export interface Codec {
  /**
   * Bytes into maps, lists and scalars.
   *
   * Text is accepted as well as bytes, because a substituted reader in a test
   * has no filesystem to have read bytes from and writing a string is what
   * makes that test four lines.
   */
  decode(data: Uint8Array | string): WrenchValue;
  /** A structure into canonical bytes. */
  encode(value: WrenchValue): Uint8Array;
}

/** The IO on the way in, handed the path rather than the bytes. */
export interface Reader {
  read(path: string): Uint8Array | string;
}

/** The IO on the way out, putting the whole contents in place. */
export interface Writer {
  write(path: string, bytes: Uint8Array): void;
}

/** Applied to the decoded structure rather than to the text. */
export interface Schema {
  validate(value: WrenchValue): void;
}

/** Bytes, whichever of the two a seam supplied. */
export function asText(data: Uint8Array | string): string {
  return typeof data === "string" ? data : new TextDecoder().decode(data);
}
