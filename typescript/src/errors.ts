/**
 * The error family. Every failure a public entry point produces is one of
 * these, carrying the underlying cause, so one `catch` reaches everything
 * wrench can throw and no consumer ever handles a `YAMLParseError` or an ajv
 * `MissingRefError`.
 *
 * A failing call says which step failed. `step` is the vocabulary a consumer
 * matches on, exposed as DATA rather than only as a class, because bolt writes
 * one into a reason's `kind` and a class name is not a value it can carry.
 *
 * THESE EXTEND `Error` AND NOTHING NARROWER. The contract forbids hanging them
 * off a language's semantic error hierarchy: a validation failure can be a
 * wrong type, which `'three' is not of type 'integer'` demonstrates, and
 * JavaScript's `TypeError` and `RangeError` each exclude half of what a schema
 * refuses. `Error` is the rescuable base rather than a claim about what went
 * wrong, which is the position every other pack takes.
 */

/** Which step of the two calls failed. Six are steps; `usage` names none. */
export type Step =
  | "read"
  | "parse"
  | "schema"
  | "validate"
  | "encode"
  | "write"
  | "usage";

/**
 * Every step word, in the order the contract lists them. Exposed so a consumer
 * can enumerate the vocabulary rather than restating it.
 */
export const STEPS: readonly Step[] = [
  "read",
  "parse",
  "schema",
  "validate",
  "encode",
  "write",
  "usage",
] as const;

/** What a wrench error can be given beyond its message. */
export interface ErrorDetail {
  /** The failure underneath, or absent where wrench itself is the whole story. */
  cause?: unknown;
  /**
   * Which file it happened to, filled in by the two calls. A codec is handed
   * bytes and a schema a structure, so neither knows which file it is working
   * on: both throw with no path and the call that knows adds it.
   */
  path?: string;
}

/** Anything wrench throws. */
export class WrenchError extends Error {
  /** Which step failed, as a word a consumer can match on. */
  readonly step: Step = "usage";
  /** The file it happened to, where the call that knew filled it in. */
  readonly path?: string;

  constructor(message: string, detail: ErrorDetail = {}) {
    super(detail.path ? `${message} (${detail.path})` : message, {
      cause: detail.cause,
    });
    // Set explicitly rather than left to the class name, so a consumer reading
    // `error.name` gets the same word whatever a bundler renamed the class to.
    this.name = new.target.name;
    this.path = detail.path;
  }

  /** The same error, told which file it happened to. */
  withPath(path: string): WrenchError {
    const Kind = this.constructor as new (
      message: string,
      detail?: ErrorDetail,
    ) => WrenchError;
    return new Kind(this.messageWithoutPath(), { cause: this.cause, path });
  }

  private messageWithoutPath(): string {
    if (this.path === undefined) return this.message;
    const suffix = ` (${this.path})`;
    return this.message.endsWith(suffix)
      ? this.message.slice(0, -suffix.length)
      : this.message;
  }
}

/** The reader could not supply the bytes. */
export class ReadError extends WrenchError {
  override readonly step: Step = "read";
}

/** The codec could not turn bytes into a structure. */
export class ParseError extends WrenchError {
  override readonly step: Step = "parse";
}

/** The schema itself could not be compiled or resolved. */
export class SchemaError extends WrenchError {
  override readonly step: Step = "schema";
}

/**
 * The structure did not match the schema.
 *
 * NOT A SUBCLASS OF `TypeError`, deliberately. Validation spans a wrong type
 * and a wrong value, and they are the same failure here.
 */
export class ValidationError extends WrenchError {
  override readonly step: Step = "validate";
}

/** The codec could not produce canonical bytes for the structure. */
export class EncodeError extends WrenchError {
  override readonly step: Step = "encode";
}

/** The writer could not put the bytes in place. */
export class WriteError extends WrenchError {
  override readonly step: Step = "write";
}

/**
 * The call was made wrongly, before any file was touched.
 *
 * The seventh kind, and the one that sits outside the two sequences: a missing
 * schema, codec, reader or writer. Rust cannot produce it because the same call
 * does not compile there. TypeScript's types say the same thing, and are
 * erased at run time, so a JavaScript caller reaches it and this pack has it.
 */
export class UsageError extends WrenchError {
  override readonly step: Step = "usage";
}
