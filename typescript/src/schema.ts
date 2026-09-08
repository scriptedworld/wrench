/**
 * Schemas, and validating a decoded structure against one.
 *
 * The schemas are the files in this repository's `schemas/` directory, carried
 * as text by `shipped.ts` rather than copied by hand. One copy is what stops
 * two producers drifting apart while both believe they conform (FR-3.2).
 *
 * `ajv` 8.20.0 is the binding, in its 2020-12 build, chosen in
 * `docs/DECISIONS/which-json-schema-library-each-pack-binds.md`. Each pack
 * binds its language's established implementation instead of implementing JSON
 * Schema itself (FR-5.2).
 *
 * Compiling is deferred until something validates, so importing wrench costs
 * nothing and a broken schema surfaces from the call that needed it.
 *
 * THE ID, NOT THE FILENAME, is what a schema is called in an error (FR-3.6). A
 * relative filename resolves against whatever directory the process happened to
 * start in, which puts a local absolute path into a message that travels inside
 * an envelope.
 *
 * A `$ref` RESOLVES FROM THE SHIPPED SET AND THE DOCUMENT'S OWN FRAGMENTS, AND
 * FROM NOWHERE ELSE (FR-3.10). ajv never retrieves anything for a synchronous
 * compile, so the refusal is structural rather than a policy this file applies:
 * there is no hook to reach the network or the disk and none is installed.
 * Measured against every shape a reference can take, including a `file://` URL
 * whose target exists.
 */

import { Ajv2020 } from "ajv/2020";
import type { ErrorObject, ValidateFunction } from "ajv";

import { SchemaError, ValidationError } from "./errors.ts";
import type { Schema, WrenchValue } from "./seams.ts";
import { SHIPPED } from "./shipped.ts";

/** A JSON Schema document, which is any JSON object. */
export type SchemaDocument = Record<string, unknown>;

/**
 * The one sentence every pack gives for a reference it will not follow
 * (FR-3.10d).
 *
 * It names the reference as RESOLVED rather than as written, because a relative
 * `$ref` resolves against the document's `$id` and the two can look nothing
 * alike: `sibling.schema.json` under an `$id` of
 * `https://elsewhere.invalid/root.json` is a reference to
 * `https://elsewhere.invalid/sibling.schema.json`, and quoting what was written
 * would send a reader looking for the wrong thing.
 */
export function unresolved(uri: string): string {
  return `cannot resolve ${uri}: a schema may reference the shipped schemas and its own fragments, and nothing else`;
}

/** Every shipped schema, keyed by the `$id` it declares. */
let shippedByIdCache: Map<string, SchemaDocument> | null = null;

function shippedById(): Map<string, SchemaDocument> {
  if (shippedByIdCache !== null) return shippedByIdCache;
  const out = new Map<string, SchemaDocument>();
  for (const name of Object.keys(SHIPPED).sort()) {
    const document = JSON.parse(SHIPPED[name]) as SchemaDocument;
    const declared = document.$id;
    if (typeof declared !== "string" || declared === "") {
      throw new Error(`wrench: shipped schema ${name} declares no $id`);
    }
    out.set(declared, document);
  }
  if (out.size === 0) throw new Error("wrench: no shipped schemas");
  shippedByIdCache = out;
  return out;
}

/**
 * A validator holding the shipped set and nothing else.
 *
 * `strict: false` because wrench's schemas use union types deliberately and
 * ajv's strict mode is a style opinion rather than a validity check, which is
 * the same setting the gate's independent check runs with.
 *
 * One instance per compiled schema rather than one shared: a shared registry
 * would make two callers compiling different documents under one name collide,
 * and the collision would surface as the second caller validating against the
 * first caller's schema.
 */
function validatorWithShipped(): Ajv2020 {
  const ajv = new Ajv2020({ strict: false, allErrors: false });
  for (const [identifier, document] of shippedById()) {
    ajv.addSchema(document, identifier);
  }
  return ajv;
}

/** The reference an ajv resolution failure was about, already resolved. */
function referenceIn(cause: unknown): string | null {
  const missing = (cause as { missingRef?: unknown }).missingRef;
  return typeof missing === "string" && missing !== "" ? missing : null;
}

/** A compiled schema, validating the maps and lists a codec produced. */
export class CompiledSchema implements Schema {
  readonly name: string;
  #document: SchemaDocument | null;
  #validate: ValidateFunction | null = null;

  constructor(name: string, document: SchemaDocument | null) {
    this.name = name;
    this.#document = document;
  }

  /**
   * Check a decoded structure, throwing `ValidationError` describing the first
   * problem and where in the document it sits.
   *
   * A schema over a large document says nothing useful without the pointer, so
   * the failure carries it. No path: `validate` is handed a structure and does
   * not know which file it came from, and the two calls fill that in.
   */
  validate(value: WrenchValue): void {
    const validate = this.#compiled();
    if (validate(value)) return;
    const first = (validate.errors ?? [])[0] as ErrorObject | undefined;
    const where = first?.instancePath ?? "";
    const at = where === "" ? "" : ` at '${where}'`;
    throw new ValidationError(
      `${this.name}${at}: ${first?.message ?? "does not match the schema"}`,
    );
  }

  /** The document, compiled on first use and kept. */
  #compiled(): ValidateFunction {
    if (this.#validate !== null) return this.#validate;
    const document = this.#document ?? this.#shipped();
    const ajv = validatorWithShipped();
    let compiled: ValidateFunction | undefined;
    try {
      // Registered under the name rather than compiled directly, because the
      // name is then the base a relative `$ref` resolves against where the
      // document declares no `$id` of its own. FR-3.10b.
      if (ajv.getSchema(this.name) === undefined) {
        ajv.addSchema(document, this.name);
      }
      compiled = ajv.getSchema(this.name);
    } catch (cause) {
      const reference = referenceIn(cause);
      throw new SchemaError(
        `${this.name}: ${
          reference === null ? (cause as Error).message : unresolved(reference)
        }`,
        { cause },
      );
    }
    if (compiled === undefined) {
      throw new SchemaError(`${this.name}: the schema did not compile`);
    }
    this.#validate = compiled;
    return compiled;
  }

  /** A shipped schema's document, read from the carried text on first use. */
  #shipped(): SchemaDocument {
    const document = shippedById().get(this.name);
    if (document === undefined) {
      throw new SchemaError(`wrench: no shipped schema declares ${this.name}`);
    }
    this.#document = document;
    return document;
  }
}

/**
 * Turn a JSON Schema document into a `Schema`.
 *
 * The shipped set are not special: anything in the ecosystem can attach a
 * schema to its own structured files and hand it to the same two calls.
 *
 * A caller's schema MAY reference a shipped one by its `$id`, because the
 * shipped set is registered before it. That is the case a consumer most wants:
 * an adapter extending the envelope schema references it rather than copying
 * it, and a copy is the drift FR-3.2 exists to prevent.
 *
 * It may reference NOTHING ELSE, and there is no way to ask for more.
 *
 * A caller may not redefine a shipped `$id` either, because a document deciding
 * what the envelope schema means defeats the reason a schema ships at all.
 */
export function compileSchema(
  name: string,
  document: string | SchemaDocument,
): CompiledSchema {
  let parsed: SchemaDocument;
  try {
    parsed = typeof document === "string"
      ? (JSON.parse(document) as SchemaDocument)
      : document;
  } catch (cause) {
    throw new SchemaError(`${name}: could not read the schema`, { cause });
  }

  const shipped = shippedById();
  const declared = typeof parsed.$id === "string" ? parsed.$id : null;
  if (shipped.has(name) || (declared !== null && shipped.has(declared))) {
    throw new SchemaError(`${name}: a shipped schema cannot be redefined`);
  }

  // Checked against the metaschema here rather than at first validate, so a
  // document that is not a schema fails where it was handed over. Reference
  // resolution stays deferred, because that is what compiling a reference
  // costs and nothing has asked for it yet.
  try {
    new Ajv2020({ strict: false }).validateSchema(parsed, true);
  } catch (cause) {
    throw new SchemaError(`${name}: ${(cause as Error).message}`, { cause });
  }

  return new CompiledSchema(name, parsed);
}

/**
 * The schemas that ship with the pack, grouped so the names carry no suffix
 * (FR-5.7).
 *
 * Each is named by its `$id` alone, which is also how every other shipped
 * schema references it. There is no filename here, so the two ways of naming
 * one schema cannot disagree.
 */
export const schemas: Readonly<Record<string, CompiledSchema>> = {
  ENVELOPE: new CompiledSchema(
    "https://scriptedworld.github.io/wrench/envelope.schema.json",
    null,
  ),
  JIG: new CompiledSchema(
    "https://scriptedworld.github.io/wrench/jig.schema.json",
    null,
  ),
  MANIFEST: new CompiledSchema(
    "https://scriptedworld.github.io/wrench/manifest.schema.json",
    null,
  ),
  DEFINITIONS: new CompiledSchema(
    "https://scriptedworld.github.io/wrench/definitions.schema.json",
    null,
  ),
};

/** Every shipped schema's `$id`, discovered from the shipped set. */
export function shippedIds(): string[] {
  return [...shippedById().keys()].sort();
}
