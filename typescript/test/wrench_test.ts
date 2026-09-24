/**
 * The TypeScript pack's suite.
 *
 * Nothing here is mocked. A reader is handed a path rather than bytes precisely
 * so a test can substitute one without a filesystem, and where a file is wanted
 * the test writes a real one into a temporary directory. `Reading` and
 * `Failing` below are readers, which is a seam the contract declares, not stand
 * ins for the code under test.
 *
 * Every test names the requirement it discharges. The kinds are `positive`,
 * `negative`, `edge`, `property` and `regression`, and `bin/test-suite-parity.py`
 * compares this set against the other packs'.
 *
 * Each `test(...)` is prefixed with `void`. `node:test` returns a promise the
 * runner itself awaits, so nothing here needs to; the operator says that in the
 * one way the linter's `no-floating-promises` accepts, and keeps the rule armed
 * for a promise that really is dropped.
 */

import assert from "node:assert/strict";
import {
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { readdir, readFile, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import process from "node:process";
import { test } from "node:test";

import * as wrench from "../src/mod.ts";
import { rendered } from "../bin/generate_shipped.ts";
import { SHIPPED } from "../src/shipped.ts";

const ROOT = new URL("../../", import.meta.url);

/**
 * What a call threw, having asserted that it threw that kind.
 *
 * `node:assert` has `throws`, which asserts and returns nothing. Most of the
 * tests below go on to read the `step`, the `path` or the message off the
 * failure, so the error itself is what is wanted. This is the only piece of
 * assertion machinery the suite needs that the standard library does not carry.
 *
 * `matching` is a substring of the message, and `detail` is what is reported
 * when nothing was thrown or the wrong kind was.
 */
function assertThrows<E extends Error>(
  step: () => unknown,
  kind: abstract new (...args: never[]) => E,
  matching?: string,
  detail?: string,
): E {
  try {
    step();
  } catch (failure) {
    assert(
      failure instanceof kind,
      detail ?? `threw ${String(failure)} rather than a ${kind.name}`,
    );
    if (matching !== undefined) {
      assert(
        failure.message.includes(matching),
        `the message does not include ${matching}: ${failure.message}`,
      );
    }
    return failure;
  }
  throw new assert.AssertionError({
    message: detail ?? `nothing was thrown, and a ${kind.name} was expected`,
  });
}

/** The shared parity tree, the same file every pack is measured against.
 *
 * It sits in `testdata/` beside the fixture set, not under `.ephemera/`, which
 * is gitignored: a suite reading a working file passes here and fails in every
 * clone, because `git archive HEAD` carries the test and not what it reads. */
const TREE = JSON.parse(
  await readFile(new URL("testdata/parity-tree.json", ROOT), "utf8"),
) as wrench.WrenchValue;

/** A schema that accepts anything, for the tests that are not about schemas. */
const ANY = wrench.compileSchema("anything", {});

/**
 * The seam a JavaScript caller passes when it passes none.
 *
 * TypeScript's types forbid it and are erased at run time, so this is what
 * reaches the `usage` kind. Cast through `unknown` rather than through `any`,
 * which says the same thing without turning the checker off for the expression.
 */
const NO_SCHEMA = null as unknown as wrench.Schema;

/** The value a caller cannot write, spelled so the types allow the call. */
const UNWRITABLE = { n: undefined } as unknown as wrench.WrenchValue;

/**
 * A reader handed a path and answering with bytes it already holds.
 *
 * This is the seam FR-2.5a exists for: handed the path rather than the bytes, a
 * substituted reader exercises decode and validate together against no
 * filesystem at all.
 */
class Reading implements wrench.Reader {
  readonly seen: string[] = [];
  // A field and an assignment rather than a parameter property. Node strips
  // types from a `.ts` file and does not transform it, and a parameter property
  // is the one piece of class syntax that has to be transformed rather than
  // erased: it declares a field and writes to it, neither of which survives
  // deleting the annotation.
  readonly data: Uint8Array | string;
  constructor(data: Uint8Array | string) {
    this.data = data;
  }
  read(path: string): Uint8Array | string {
    this.seen.push(path);
    return this.data;
  }
}

/** A reader that cannot supply the bytes, which is the `read` step failing. */
class Failing implements wrench.Reader {
  read(path: string): Uint8Array {
    throw new wrench.ReadError("no such file", { path });
  }
}

/** A writer that records rather than writing, for the seam tests. */
class Recording implements wrench.Writer {
  readonly seen: [string, string][] = [];
  write(path: string, bytes: Uint8Array): void {
    this.seen.push([path, new TextDecoder().decode(bytes)]);
  }
}

function text(bytes: Uint8Array): string {
  return new TextDecoder().decode(bytes);
}

function withDirectory(step: (dir: string) => void): void {
  const dir = mkdtempSync(join(tmpdir(), "wrench-ts-"));
  try {
    step(dir);
  } finally {
    rmSync(dir, { recursive: true });
  }
}

const VALID_ENVELOPE = "success: true\n";
const VALID_JIG = 'tasks:\n  - name: check\n    command: "true"\n';

// ---- what wrench is ---------------------------------------------------------

// COVERS: FR-1.1 | positive
void test("the pack reads the one copy of the schemas", async () => {
  // The schemas and a library for each language live in one repository, so two
  // producers work from the same definition. The pack carries their text rather
  // than resolving a path, so what makes that true is the carried copy being
  // byte for byte the directory's.
  for (const name of Object.keys(SHIPPED)) {
    const onDisk = await readFile(new URL(`schemas/${name}`, ROOT), "utf8");
    assert.deepEqual(
      SHIPPED[name],
      onDisk,
      `${name} differs from schemas/${name}`,
    );
  }
  assert(Object.keys(SHIPPED).length > 0, "no schemas are carried");
});

// COVERS: FR-1.2 | negative
void test("a key that is not a string is refused rather than coerced", () => {
  // wrench establishes that a file has the FORM its schema declares. A mapping
  // key that is not a string has no JSON equivalent, and stringifying it
  // invents a document nobody wrote, so it is refused at the decoder.
  const failure = assertThrows(
    () => wrench.YAML.decode("1: x\n"),
    wrench.ParseError,
  );
  assert.deepEqual(failure.step, "parse");
  // Quoted, the same key is a string and is taken.
  assert.deepEqual(wrench.YAML.decode('"1": x\n'), { "1": "x" });
});

// COVERS: FR-1.4 | negative
void test("an envelope missing success is refused", () => {
  // Validation is JSON Schema over the decoded structure, and wrench does not
  // get to differ from that decision. This is where it is implemented.
  const failure = assertThrows(
    () =>
      wrench.loadFormattedFile(
        "output.yaml",
        wrench.schemas.ENVELOPE,
        wrench.YAML,
        new Reading("reasons: []\n"),
      ),
    wrench.ValidationError,
  );
  assert(
    failure.message.includes("success"),
    `does not name the missing key: ${failure.message}`,
  );
});

// ---- the two calls ----------------------------------------------------------

// COVERS: FR-2.1 | positive
void test("the two calls round trip a document", () => {
  withDirectory((dir) => {
    const path = `${dir}/doc.yaml`;
    wrench.saveYamlFile(TREE, path, ANY, wrench.LOCAL_FILE);
    assert.deepEqual(wrench.loadYamlFile(path, ANY, wrench.LOCAL_FILE), TREE);
  });
});

// COVERS: FR-2.2 | positive
void test("validation sits in the signature", () => {
  // Nothing reads or writes without naming what the file must conform to, so
  // conformance is a property of the call rather than of remembering to check.
  const reader = new Reading(VALID_ENVELOPE);
  wrench.loadFormattedFile(
    "f.yaml",
    wrench.schemas.ENVELOPE,
    wrench.YAML,
    reader,
  );
  assert.deepEqual(reader.seen, ["f.yaml"]);
});

// COVERS: FR-2.2 | negative
void test("a missing seam is usage and touches no file", () => {
  withDirectory((dir) => {
    const path = `${dir}/doc.yaml`;
    const failure = assertThrows(
      () => wrench.loadYamlFile(path, NO_SCHEMA, wrench.LOCAL_FILE),
      wrench.UsageError,
    );
    assert.deepEqual(failure.step, "usage");
    assert.deepEqual(
      readdirSync(dir).length,
      0,
      "nothing should have been written",
    );
  });
});

// COVERS: FR-2.3 | negative
void test("a call with no schema is refused, and the wrong one is not detected", () => {
  // The signature compels a schema, not the right one. Passing none is
  // impossible; passing the wrong one is not, and no part of the library
  // detects that.
  for (const attempt of [
    () =>
      wrench.loadFormattedFile(
        "f.yaml",
        NO_SCHEMA,
        wrench.YAML,
        new Reading(""),
      ),
    () =>
      wrench.saveFormattedFile(
        {},
        "f.yaml",
        NO_SCHEMA,
        wrench.YAML,
        new Recording(),
      ),
  ]) {
    const failure = assertThrows(attempt, wrench.UsageError);
    assert(failure.message.includes("no schema"), failure.message);
  }

  // A jig validated against the definitions schema: the wrong schema, and
  // nothing here can tell.
  wrench.loadFormattedFile(
    "bolt.q.yaml",
    wrench.compileSchema("permissive", { type: "object" }),
    wrench.YAML,
    new Reading(VALID_JIG),
  );
});

// COVERS: FR-2.4 | positive
void test("what a save wrote survives a load", () => {
  withDirectory((dir) => {
    const path = `${dir}/out.yaml`;
    const value = { success: true, metadata: { statistics: { checked: 12 } } };
    wrench.saveFormattedFile(
      value,
      path,
      wrench.schemas.ENVELOPE,
      wrench.YAML,
      wrench.LOCAL_FILE,
    );
    assert.deepEqual(
      wrench.loadFormattedFile(
        path,
        wrench.schemas.ENVELOPE,
        wrench.YAML,
        wrench.LOCAL_FILE,
      ),
      value,
    );
  });
});

// COVERS: FR-2.4 | negative
void test("a structure the schema refuses is not written", () => {
  const schema = wrench.compileSchema("needs a name", {
    type: "object",
    required: ["name"],
  });
  withDirectory((dir) => {
    const path = `${dir}/doc.yaml`;
    const failure = assertThrows(
      () => wrench.saveYamlFile({ other: 1 }, path, schema, wrench.LOCAL_FILE),
      wrench.ValidationError,
    );
    assert.deepEqual(failure.step, "validate");
    assert.deepEqual(
      readdirSync(dir).length,
      0,
      "a refused structure reached the file",
    );
  });
});

// COVERS: FR-2.5 | positive
void test("the codec and the IO are separate seams", () => {
  // One format against two sources, and one source against two formats, with
  // nothing invented on either side to make the combinations work.
  assert.deepEqual(
    wrench.loadFormattedFile("a", ANY, wrench.YAML, new Reading("k: 1\n")),
    { k: 1 },
  );
  assert.deepEqual(
    wrench.loadFormattedFile("a", ANY, wrench.JSON, new Reading('{"k": 1}')),
    { k: 1 },
  );
});

// COVERS: FR-2.5a | positive
void test("a reader is handed the path and can be substituted", () => {
  // No filesystem at all. This is what handing the reader a path rather than
  // bytes buys: a substituted reader exercises decode and validate together.
  const reader = new Reading('{"k": 1}');
  assert.deepEqual(wrench.loadJsonFile("some/path", ANY, reader), { k: 1 });
  assert.deepEqual(reader.seen, ["some/path"]);
});

// COVERS: FR-2.5a | property
void test("every step is reachable through a substituted reader", () => {
  assert.deepEqual(
    assertThrows(
      () => wrench.loadYamlFile("f.yaml", ANY, new Failing()),
      wrench.ReadError,
    ).step,
    "read",
  );
  assert.deepEqual(
    assertThrows(
      () =>
        wrench.loadYamlFile("f.yaml", ANY, new Reading("a: [unterminated\n")),
      wrench.ParseError,
    ).step,
    "parse",
  );
  assert.deepEqual(
    assertThrows(
      () =>
        wrench.loadYamlFile(
          "f.yaml",
          wrench.schemas.ENVELOPE,
          new Reading('success: "yes"\n'),
        ),
      wrench.ValidationError,
    ).step,
    "validate",
  );
});

// COVERS: FR-2.6 | negative
void test("a failure says which step failed", () => {
  assertThrows(
    () =>
      wrench.loadFormattedFile(
        "gone.yaml",
        wrench.schemas.ENVELOPE,
        wrench.YAML,
        new Failing(),
      ),
    wrench.ReadError,
  );
  assertThrows(
    () =>
      wrench.loadFormattedFile(
        "f.yaml",
        wrench.schemas.ENVELOPE,
        wrench.YAML,
        new Reading("success: [unterminated\n"),
      ),
    wrench.ParseError,
  );
  assertThrows(
    () =>
      wrench.loadFormattedFile(
        "f.yaml",
        wrench.schemas.ENVELOPE,
        wrench.YAML,
        new Reading('success: "yes"\n'),
      ),
    wrench.ValidationError,
  );
});

// COVERS: FR-2.7 | positive
void test("two codecs ship and both round trip the shared tree", () => {
  for (const codec of [wrench.YAML, wrench.JSON]) {
    assert.deepEqual(codec.decode(codec.encode(TREE)), TREE);
  }
});

// COVERS: FR-2.7 | property
void test("both codecs decode to one structure", () => {
  // The codec argument exists so that one schema validates a file whichever
  // codec read it, which only holds if the two produce the same value model.
  assert.deepEqual(
    wrench.YAML.decode(wrench.YAML.encode(TREE)),
    wrench.JSON.decode(wrench.JSON.encode(TREE)),
  );
});

// COVERS: FR-2.8 | positive
void test("one local reader and one local writer ship", () => {
  withDirectory((dir) => {
    const path = `${dir}/out.yaml`;
    wrench.LOCAL_FILE.write(path, new TextEncoder().encode("success: true\n"));
    assert.deepEqual(text(wrench.LOCAL_FILE.read(path)), "success: true\n");
  });
});

// COVERS: FR-2.9 | regression
void test("a timestamp decodes to a string so it can be written back", () => {
  // YAML has a native timestamp type and JSON does not. A date decoding to a
  // date object reaches the validator, which has no type for it, and then
  // cannot be encoded: wrench would read a file it could not write back.
  const value = wrench.YAML.decode(
    "day: 2026-01-01\nstamp: 2026-01-01T07:32:00Z\n",
  ) as Record<string, unknown>;
  for (const name of ["day", "stamp"]) {
    assert.deepEqual(
      typeof value[name],
      "string",
      `${name} did not decode to a string`,
    );
  }
  const encoded = wrench.YAML.encode(value as wrench.WrenchValue);
  assert.deepEqual(
    wrench.YAML.encode(wrench.YAML.decode(encoded)),
    encoded,
    "not a fixed point",
  );
});

// COVERS: FR-2.10 | positive
void test("a wrapper per format supplies the codec and adds nothing else", () => {
  withDirectory((dir) => {
    const value = { success: true };
    wrench.saveYamlFile(
      value,
      `${dir}/a.yaml`,
      wrench.schemas.ENVELOPE,
      wrench.LOCAL_FILE,
    );
    wrench.saveJsonFile(
      value,
      `${dir}/a.json`,
      wrench.schemas.ENVELOPE,
      wrench.LOCAL_FILE,
    );
    assert.deepEqual(
      wrench.loadYamlFile(
        `${dir}/a.yaml`,
        wrench.schemas.ENVELOPE,
        wrench.LOCAL_FILE,
      ),
      value,
    );
    assert.deepEqual(
      wrench.loadJsonFile(
        `${dir}/a.json`,
        wrench.schemas.ENVELOPE,
        wrench.LOCAL_FILE,
      ),
      value,
    );
  });
});

// COVERS: FR-2.10 | negative
void test("a wrapper still validates, so the seam is unchanged in both directions", () => {
  assertThrows(
    () =>
      wrench.loadYamlFile(
        "f.yaml",
        wrench.schemas.ENVELOPE,
        new Reading("reasons: []\n"),
      ),
    wrench.ValidationError,
  );
  withDirectory((dir) => {
    assertThrows(
      () =>
        wrench.saveJsonFile(
          { reasons: [] },
          `${dir}/a.json`,
          wrench.schemas.ENVELOPE,
          wrench.LOCAL_FILE,
        ),
      wrench.ValidationError,
    );
  });
});

// COVERS: FR-2.11 | property
void test("every failure is one family with a step", () => {
  assert.deepEqual(
    [...wrench.STEPS],
    ["read", "parse", "schema", "validate", "encode", "write", "usage"],
  );
  const kinds: [new (message: string) => wrench.WrenchError, wrench.Step][] = [
    [wrench.ReadError, "read"],
    [wrench.ParseError, "parse"],
    [wrench.SchemaError, "schema"],
    [wrench.ValidationError, "validate"],
    [wrench.EncodeError, "encode"],
    [wrench.WriteError, "write"],
    [wrench.UsageError, "usage"],
  ];
  for (const [Kind, step] of kinds) {
    const failure = new Kind("x");
    assert.deepEqual(failure.step, step);
    assert(
      failure instanceof wrench.WrenchError,
      `${step} is outside the family`,
    );
    assert(failure instanceof Error, `${step} is not an Error`);
  }
});

// COVERS: FR-2.11 | negative
void test("an error names the file and keeps the cause", () => {
  // A codec is handed bytes and a schema a structure, so neither knows which
  // file it is working on. The two calls fill it in.
  const failure = assertThrows(
    () =>
      wrench.loadJsonFile("some/where.json", ANY, new Reading("{ not json")),
    wrench.ParseError,
  );
  assert.deepEqual(failure.step, "parse");
  assert.deepEqual(failure.path, "some/where.json");
  assert(failure.message.includes("some/where.json"), failure.message);
  assert(failure.cause !== undefined, "the underlying cause was dropped");
});

// ---- the schemas ------------------------------------------------------------

// COVERS: FR-3.1, FR-3.2, FR-3.5 | positive
void test("all four shipped schemas validate from the one copy", () => {
  wrench.schemas.ENVELOPE.validate({ success: true });
  wrench.schemas.JIG.validate({
    tasks: [{ name: "build", command: "deno check" }],
  });
  wrench.schemas.DEFINITIONS.validate({ requirements: "../REQUIREMENTS.md" });
  wrench.schemas.MANIFEST.validate({
    task: "format",
    ordinal: 0,
    command: "gofmt -l a.go",
    variables: {
      project_root: { value: "/p", from: "bolt" },
      base_dir: { value: "/p/go", from: "bolt" },
      work_dir: { value: "/p/.bolt/work/format-0001", from: "bolt" },
      config_dir: { value: "/p", from: "bolt" },
      output_dir: { value: "/p/.bolt", from: "bolt" },
    },
  });
});

// COVERS: FR-3.1 | negative
void test("a document of the wrong shape is refused by its own schema", () => {
  assertThrows(
    () => wrench.schemas.JIG.validate({ tasks: [{ name: "build" }] }),
    wrench.ValidationError,
  );
});

// COVERS: FR-3.1, FR-3.4 | edge
void test("a schema checks shape and not meaning", () => {
  // A reason whose message is empty is the right type and says nothing, so it
  // passes. Anything relying on a schema to catch a wrong value is relying on
  // the wrong control.
  wrench.loadFormattedFile(
    "f.yaml",
    wrench.schemas.ENVELOPE,
    wrench.YAML,
    new Reading('success: false\nreasons:\n  - kind: k\n    message: ""\n'),
  );
});

// COVERS: FR-3.2 | negative
void test("a definitions file takes one level of scalars", () => {
  wrench.loadFormattedFile(
    "d.yaml",
    wrench.schemas.DEFINITIONS,
    wrench.YAML,
    new Reading(
      'requirements: ../REQUIREMENTS.md\nline_length: 100\nstrict: true\nempty: ""\n',
    ),
  );
  const refused: Record<string, string> = {
    "a list value": "tags:\n  - one\n  - two\n",
    "a nested value": "python:\n  line_length: 100\n",
    "a hyphenated name": "line-length: 100\n",
    "a leading underscore": "_leading: 1\n",
  };
  for (const [what, document] of Object.entries(refused)) {
    assertThrows(
      () =>
        wrench.loadFormattedFile(
          "d.yaml",
          wrench.schemas.DEFINITIONS,
          wrench.YAML,
          new Reading(document),
        ),
      wrench.ValidationError,
      undefined,
      `${what} was accepted`,
    );
  }
});

// COVERS: FR-3.2 | regression
void test("a validation error names the schema by id and not by a local path", () => {
  // The identifier lands in the error, the error lands in a reason, and a
  // reason travels as evidence to another machine.
  const failure = assertThrows(
    () =>
      wrench.loadFormattedFile(
        "f.yaml",
        wrench.schemas.ENVELOPE,
        wrench.YAML,
        new Reading('success: "yes"\n'),
      ),
    wrench.ValidationError,
  );
  assert(
    failure.message.includes(
      "scriptedworld.github.io/wrench/envelope.schema.json",
    ),
    failure.message,
  );
  assert(
    !failure.message.includes(ROOT.pathname),
    "the error carries a local filesystem path",
  );
});

// COVERS: FR-3.3 | positive
void test("one schema validates a document whichever codec read it", () => {
  const asYaml = wrench.loadFormattedFile(
    "f.yaml",
    wrench.schemas.ENVELOPE,
    wrench.YAML,
    new Reading("success: false\nreasons:\n  - kind: k\n    message: m\n"),
  );
  const asJson = wrench.loadFormattedFile(
    "f.json",
    wrench.schemas.ENVELOPE,
    wrench.JSON,
    new Reading(
      '{"success": false, "reasons": [{"kind": "k", "message": "m"}]}',
    ),
  );
  assert.deepEqual(asYaml, asJson);
});

// COVERS: FR-3.3 | negative
void test("the same document is refused whichever codec read it", () => {
  for (const [codec, document] of [
    [wrench.YAML, 'success: "yes"\n'],
    [wrench.JSON, '{"success": "yes"}'],
  ] as [wrench.Codec, string][]) {
    assertThrows(
      () =>
        wrench.loadFormattedFile(
          "f",
          wrench.schemas.ENVELOPE,
          codec,
          new Reading(document),
        ),
      wrench.ValidationError,
    );
  }
});

// COVERS: FR-3.3 | property
void test("validation is indifferent to serialisation", () => {
  // Block and flow are the same structure, so the schema cannot tell them
  // apart. Flow is not what wrench emits and is still what it reads.
  for (const document of [
    "success: false\nreasons:\n  - kind: k\n    message: m\n",
    "{success: false, reasons: [{kind: k, message: m}]}\n",
  ]) {
    wrench.loadFormattedFile(
      "f.yaml",
      wrench.schemas.ENVELOPE,
      wrench.YAML,
      new Reading(document),
    );
  }
});

// COVERS: FR-3.4 | edge
void test("a value that parsed differently from how it was written still validates", () => {
  // `1.20` unquoted is the number 1.2 and is a number of the right type, so
  // validation passes it. Quoting is what marks intent, not the schema.
  wrench.loadFormattedFile(
    "f.yaml",
    wrench.compileSchema("a version", {
      type: "object",
      properties: { version: { type: "number" } },
    }),
    wrench.YAML,
    new Reading("version: 1.20\n"),
  );
});

// COVERS: FR-3.5 | positive
void test("the schemas are files in the tree and the pack carries those bytes", async () => {
  for (const name of Object.keys(SHIPPED)) {
    const info = await stat(new URL(`schemas/${name}`, ROOT));
    assert(info.isFile(), `schemas/${name} is not a file`);
  }
});

// COVERS: FR-3.6 | positive
void test("a shipped schema may reference another and it resolves offline", () => {
  // The jig's definitions block and the definitions file are one shape, written
  // once and referenced across two shipped schemas. A jig carrying a nested
  // value has to be refused by a rule the jig schema does not itself state,
  // which is what proves the reference between them resolved.
  wrench.loadFormattedFile(
    "bolt.q.yaml",
    wrench.schemas.JIG,
    wrench.YAML,
    new Reading(
      'definitions:\n  requirements: REQUIREMENTS.md\n  line_length: 100\ntasks:\n  - name: check\n    command: "true"\n',
    ),
  );
  assertThrows(
    () =>
      wrench.loadFormattedFile(
        "bolt.q.yaml",
        wrench.schemas.JIG,
        wrench.YAML,
        new Reading(
          'definitions:\n  python:\n    line_length: 100\ntasks:\n  - name: check\n    command: "true"\n',
        ),
      ),
    wrench.ValidationError,
  );
});

// COVERS: FR-3.7, FR-5.7 | regression
void test("the carried set is the directory, regenerated rather than believed", async () => {
  // A schema added to schemas/ and picked up by one pack but not another is a
  // divergence in the contract that nothing reports. It has happened: a fourth
  // schema shipped and one pack named three filenames.
  //
  // The generator reads the directory, so running it here and comparing is the
  // same check `bin/generate-shipped.py --check` is for the other packs, and it
  // runs wherever the suite runs.
  const fromDirectory = new Map<string, string>();
  const names: string[] = [];
  const entries = await readdir(new URL("schemas/", ROOT), {
    withFileTypes: true,
  });
  for (const entry of entries) {
    if (entry.isFile() && entry.name.endsWith(".schema.json")) {
      names.push(entry.name);
    }
  }
  for (const name of names.sort()) {
    fromDirectory.set(
      name,
      await readFile(new URL(`schemas/${name}`, ROOT), "utf8"),
    );
  }
  const onDisk = await readFile(
    new URL("src/shipped.ts", new URL("../", import.meta.url)),
    "utf8",
  );
  assert.deepEqual(
    onDisk,
    rendered(fromDirectory),
    "src/shipped.ts is stale, run `npm run shipped`",
  );

  // And every one of them is exported, by the $id it declares.
  const declared = new Set<string>();
  for (const textOf of fromDirectory.values()) {
    declared.add((JSON.parse(textOf) as { $id: string }).$id);
  }
  assert.deepEqual(new Set(wrench.shippedIds()), declared);
  assert.deepEqual(
    new Set(Object.values(wrench.schemas).map((schema) => schema.name)),
    declared,
    "a shipped schema is not exported under a name",
  );
});

// COVERS: FR-3.8 | positive
void test("every shipped schema has a fixture that is an instance of it", async () => {
  // The fixture set names its schema in a `schema` file beside the input, so
  // the pack is asked the question the fixture was written to ask.
  const byId = new Map(
    Object.values(wrench.schemas).map((schema) => [schema.name, schema]),
  );
  let checked = 0;
  const entries = await readdir(new URL("testdata/canonical/", ROOT), {
    withFileTypes: true,
  });
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    let named: string;
    try {
      named = (
        await readFile(
          new URL(`testdata/canonical/${entry.name}/schema`, ROOT),
          "utf8",
        )
      ).trim();
    } catch {
      continue;
    }
    const schema =
      byId.get(named) ??
      byId.get(`https://scriptedworld.github.io/wrench/${named}.schema.json`);
    assert(
      schema !== undefined,
      `${entry.name} names a schema no pack exports: ${named}`,
    );
    const input = await readFile(
      new URL(`testdata/canonical/${entry.name}/input.yaml`, ROOT),
    );
    schema.validate(wrench.YAML.decode(input));
    checked += 1;
  }
  assert(checked > 0, "no fixture declares a schema, so this asserts nothing");
});

// COVERS: FR-3.9 | edge
void test("a document may declare the version it conforms to", () => {
  // Optional, because every document written before the field existed carries
  // none. Present, it is semver, so a consumer can refuse a major rather than
  // failing later on a field it cannot find.
  const accepted = [
    "1.0.0",
    "0.1.0",
    "10.20.30",
    "1.0.0-alpha.1",
    "1.0.0+build.5",
    "1.0.0-rc.1+build.5",
  ];
  const refused = [
    "1",
    "1.0",
    "v1.0.0",
    "1.0.0.0",
    "01.0.0",
    "",
    "latest",
    "1.0.0-",
  ];

  for (const [schema, rest] of [
    [wrench.schemas.ENVELOPE, VALID_ENVELOPE],
    [wrench.schemas.JIG, VALID_JIG],
  ] as const) {
    wrench.loadFormattedFile("f.yaml", schema, wrench.YAML, new Reading(rest));
    for (const version of accepted) {
      wrench.loadFormattedFile(
        "f.yaml",
        schema,
        wrench.YAML,
        new Reading(`version: "${version}"\n${rest}`),
      );
    }
    for (const version of refused) {
      assertThrows(
        () =>
          wrench.loadFormattedFile(
            "f.yaml",
            schema,
            wrench.YAML,
            new Reading(`version: "${version}"\n${rest}`),
          ),
        wrench.ValidationError,
        undefined,
        `${JSON.stringify(version)} was accepted as a version`,
      );
    }
  }
});

// COVERS: FR-3.9 | property
void test("the version field is the same in every format that carries it", async () => {
  // Written into each schema rather than referenced, because it constrains a
  // scalar rather than describing a shape. Repetition is the cost, so drift is
  // what this checks.
  const seen: Record<string, unknown> = {};
  for (const name of Object.keys(SHIPPED)) {
    const properties =
      (JSON.parse(SHIPPED[name]) as { properties?: Record<string, unknown> })
        .properties ?? {};
    if ("version" in properties) seen[name] = properties.version;
  }
  assert(
    Object.keys(seen).length > 0,
    "no shipped schema declares a version field",
  );
  const first = Object.keys(seen)[0];
  for (const name of Object.keys(seen)) {
    assert.deepEqual(
      seen[name],
      seen[first],
      `the version field in ${name} differs from the one in ${first}`,
    );
  }
  await Promise.resolve();
});

// ---- references -------------------------------------------------------------

/** The sentence FR-3.10d requires of every pack, held as a constant so a change to the wording fails a test. */
const REFUSAL =
  "a schema may reference the shipped schemas and its own fragments, and nothing else";

/** A schema that really is on disk, so "it was not read" is a measurement. */
function reachableSchema(): string {
  const path = join(tmpdir(), "wrench-ts-reachable.schema.json");
  writeFileSync(
    path,
    JSON.stringify({
      $schema: "https://json-schema.org/draft/2020-12/schema",
      type: "object",
      required: ["proof_it_resolved"],
    }),
  );
  return path;
}

/** What happened, rather than an assertion, so a table states its own expectation. */
function outcome(
  name: string,
  body: wrench.SchemaDocument,
  instance: wrench.WrenchValue,
): [string, string] {
  let schema: wrench.CompiledSchema;
  try {
    schema = wrench.compileSchema(name, body);
  } catch (error) {
    return ["schema", (error as Error).message];
  }
  try {
    schema.validate(instance);
  } catch (error) {
    return [(error as wrench.WrenchError).step, (error as Error).message];
  }
  return ["accepted", ""];
}

// COVERS: FR-3.10 | positive
void test("a caller's schema may reference a shipped one by its $id", () => {
  const [got, detail] = outcome(
    "https://example.invalid/s.schema.json",
    {
      $schema: "https://json-schema.org/draft/2020-12/schema",
      $ref: "https://scriptedworld.github.io/wrench/envelope.schema.json",
    },
    { success: true },
  );
  assert.deepEqual(got, "accepted", detail);
});

// COVERS: FR-3.10 | negative
void test("no environment variable opens a reference", () => {
  // WRENCH_ALLOW_EXTERNAL_SCHEMA_REFS was documented before it was retired, so
  // somebody may still set it. It meant three different things while it
  // existed, and it means nothing here.
  const reachable = reachableSchema();
  for (const name of [
    "WRENCH_ALLOW_EXTERNAL_SCHEMA_REFS",
    "WRENCH_ALLOW_LOCAL_SCHEMA_REFS",
    "WRENCH_ALLOW_NET_SCHEMA_REFS",
  ]) {
    const previous = process.env[name];
    process.env[name] = "1";
    try {
      const [got] = outcome(
        "https://example.invalid/s.schema.json",
        {
          $schema: "https://json-schema.org/draft/2020-12/schema",
          $ref: `file://${reachable}`,
        },
        { anything: 1 },
      );
      assert.deepEqual(got, "schema", `${name}=1 opened a reference`);
    } finally {
      if (previous === undefined) delete process.env[name];
      else process.env[name] = previous;
    }
  }
});

// COVERS: FR-3.10 | edge
void test("a shipped $id cannot be redefined by a caller", () => {
  // A document deciding what the envelope schema means defeats the reason a
  // schema ships at all.
  const failure = assertThrows(
    () =>
      wrench.compileSchema("mine", {
        $schema: "https://json-schema.org/draft/2020-12/schema",
        $id: "https://scriptedworld.github.io/wrench/jig.schema.json",
        type: "string",
      }),
    wrench.SchemaError,
  );
  assert.deepEqual(failure.step, "schema");
});

// COVERS: FR-3.10a | positive
void test("a reference within the document resolves", () => {
  // Both spellings, each asserted by its VIOLATION: an accepted document says
  // nothing, because a $ref that contributed no constraint would accept it too.
  const bodies: [string, wrench.SchemaDocument][] = [
    [
      "a pointer into $defs",
      {
        $schema: "https://json-schema.org/draft/2020-12/schema",
        $defs: { tight: { type: "string", minLength: 3 } },
        type: "object",
        properties: { a: { $ref: "#/$defs/tight" } },
      },
    ],
    [
      "an $anchor",
      {
        $schema: "https://json-schema.org/draft/2020-12/schema",
        $defs: { t: { $anchor: "tight", type: "string", minLength: 3 } },
        type: "object",
        properties: { a: { $ref: "#tight" } },
      },
    ],
  ];
  for (const [what, body] of bodies) {
    const name = "https://example.invalid/s.schema.json";
    assert.deepEqual(
      outcome(name, body, { a: "abc" })[0],
      "accepted",
      `${what} refused a document it should take`,
    );
    assert.deepEqual(
      outcome(name, body, { a: "x" })[0],
      "validate",
      `${what} did not constrain, so the reference resolved to nothing`,
    );
  }
});

// COVERS: FR-3.10b, FR-3.10d | negative
void test("a refusal names the resolved reference", () => {
  // A relative reference resolves against the document's $id, so the text and
  // the reference are different strings. This also pins that the $id wins over
  // the compile name.
  const [got, detail] = outcome(
    "mine.schema.json",
    {
      $schema: "https://json-schema.org/draft/2020-12/schema",
      $id: "https://elsewhere.invalid/root.schema.json",
      $ref: "sibling.schema.json",
    },
    { anything: 1 },
  );
  assert.deepEqual(
    got,
    "schema",
    `a reference outside the shipped set resolved: ${detail}`,
  );
  assert(
    detail.includes("https://elsewhere.invalid/sibling.schema.json"),
    detail,
  );
  assert(detail.includes(REFUSAL), detail);
});

// COVERS: FR-3.10c | negative
void test("a keyword in an instance is data", () => {
  // The schema keywords are ordinary keys in a document being validated. The
  // file this points at EXISTS, so an implementation that resolved it is caught
  // here rather than passing for want of a target.
  const reachable = reachableSchema();
  const instances: [string, wrench.WrenchValue][] = [
    ["a $ref at a file that exists", { $ref: `file://${reachable}` }],
    ["a $ref at an http url", { $ref: "http://example.invalid/x.schema.json" }],
    ["an $id", { $id: "https://example.invalid/other" }],
    ["a $schema", { $schema: "https://json-schema.org/draft/2020-12/schema" }],
    [
      "a document that is a schema",
      {
        $schema: "https://json-schema.org/draft/2020-12/schema",
        $id: "https://example.invalid/embedded",
        $ref: `file://${reachable}`,
      },
    ],
  ];
  for (const [what, instance] of instances) {
    const [got, detail] = outcome(
      "https://example.invalid/s.schema.json",
      {
        $schema: "https://json-schema.org/draft/2020-12/schema",
        type: "object",
      },
      instance,
    );
    assert.deepEqual(
      got,
      "accepted",
      `${what} in an instance was interpreted: ${got}: ${detail}`,
    );
  }
});

// COVERS: FR-3.10d | negative
void test("every refused form gives the same sentence", () => {
  // One sentence for every shape a reference can take, so a consumer matching
  // on the failure does not need a list of the ways it can be spelled.
  const reachable = reachableSchema();
  const refs: [string, string][] = [
    ["an http url", "http://example.invalid/x.schema.json"],
    ["an https url", "https://example.invalid/x.schema.json"],
    ["a file url", `file://${reachable}`],
    ["an absolute path", reachable],
    ["a relative path", "sibling.schema.json"],
    [
      "an unshipped wrench",
      "https://scriptedworld.github.io/wrench/not-shipped.schema.json",
    ],
  ];
  for (const [what, ref] of refs) {
    const [got, detail] = outcome(
      "https://example.invalid/s.schema.json",
      {
        $schema: "https://json-schema.org/draft/2020-12/schema",
        $ref: ref,
      },
      { anything: 1 },
    );
    assert.deepEqual(
      got,
      "schema",
      `${what} resolved rather than being refused`,
    );
    assert(
      detail.includes(REFUSAL),
      `${what} was refused in different words: ${detail}`,
    );
  }
});

// ---- canonical form ---------------------------------------------------------

// COVERS: FR-4.1 | property
void test("a scalar is quoted exactly when it is meant to be a string", () => {
  // Unquoted, a YAML reader takes each of these for something else, and `1.20`
  // loses its trailing zero as a number.
  const tricky = {
    a: "no",
    b: "yes",
    c: "on",
    d: "null",
    e: "~",
    f: "1.20",
    g: "007",
    h: "12:30:45",
    i: "2026-01-01",
  };
  assert.deepEqual(wrench.YAML.decode(wrench.YAML.encode(tricky)), tricky);
  // And the types that are not strings stay unquoted, so they come back as
  // themselves rather than as their spelling.
  const typed = { n: 1, f: 2.5, t: true, z: null };
  assert.deepEqual(wrench.YAML.decode(wrench.YAML.encode(typed)), typed);
  const written = text(wrench.YAML.encode(typed));
  assert.deepEqual(written, '"f": 2.5\n"n": 1\n"t": true\n"z": null\n');
});

// COVERS: FR-4.1 | edge
void test("a numeric key stays a string", () => {
  // Sharper than the value case: to a YAML 1.1 reader an unquoted `10:` is an
  // integer key, so the key is quoted too.
  const subject = { "10": 1, "2": 2 };
  assert.deepEqual(wrench.YAML.decode(wrench.YAML.encode(subject)), subject);
  assert(text(wrench.YAML.encode(subject)).startsWith('"10": 1\n"2": 2\n'));
});

// COVERS: FR-4.1 | negative
void test("a value with no canonical form is refused rather than guessed at", () => {
  for (const value of [NaN, Infinity, -Infinity]) {
    for (const codec of [wrench.YAML, wrench.JSON]) {
      assertThrows(() => codec.encode({ n: value }), wrench.EncodeError);
    }
  }
  for (const codec of [wrench.YAML, wrench.JSON]) {
    assertThrows(() => codec.encode(UNWRITABLE), wrench.EncodeError);
  }
});

// COVERS: FR-4.2 | property
void test("a string survives the round trip as the string it was", () => {
  const strings = [
    "no",
    "yes",
    "on",
    "off",
    "null",
    "~",
    "1.20",
    "007",
    "12:30:45",
    "",
    " ",
    "\n",
    "a\tb",
  ];
  const subject = Object.fromEntries(strings.map((s, i) => [`k${i}`, s]));
  for (const codec of [wrench.YAML, wrench.JSON]) {
    assert.deepEqual(
      codec.decode(codec.encode(subject)),
      subject,
      "a string changed type",
    );
  }
});

// COVERS: FR-4.3 | positive
void test("canonical form belongs to the save call", () => {
  // A caller cannot emit something valid but written another way: the save call
  // writes canonical form whatever the structure was built from.
  const recorder = new Recording();
  wrench.saveYamlFile({ z: 1, a: 2 }, "out.yaml", ANY, recorder);
  assert.deepEqual(recorder.seen, [["out.yaml", '"a": 2\n"z": 1\n']]);
});

// COVERS: FR-4.3 | property
void test("keys are sorted so two runs agree", () => {
  for (const codec of [wrench.YAML, wrench.JSON]) {
    assert.deepEqual(
      codec.encode({ z: 1, a: 2, m: 3 }),
      codec.encode({ m: 3, a: 2, z: 1 }),
    );
  }
  // Sorted as strings, which is what puts `10` before `2`. A JavaScript object
  // enumerates an integer-like key first whatever order it was built in, so
  // this is the case the ordering adapter exists for.
  assert.deepEqual(
    text(wrench.JSON.encode({ "2": 1, "10": 2, Mango: 3, apple: 4 })),
    '{\n  "10": 2,\n  "2": 1,\n  "Mango": 3,\n  "apple": 4\n}\n',
  );
});

// COVERS: FR-4.4 | property
void test("flow style is not what wrench emits", () => {
  const written = text(wrench.YAML.encode({ items: [1, 2], nested: { a: 1 } }));
  assert.deepEqual(written, '"items":\n  - 1\n  - 2\n"nested":\n  "a": 1\n');
  // An empty collection has no block spelling, which is the one exception and
  // is what every pack writes.
  assert.deepEqual(
    text(wrench.YAML.encode({ a: {}, b: [] })),
    '"a": {}\n"b": []\n',
  );
});

// COVERS: FR-4.5 | property
void test("a structure round trips through both codecs and the filesystem", () => {
  withDirectory((dir) => {
    for (const [name, save, load] of [
      ["doc.yaml", wrench.saveYamlFile, wrench.loadYamlFile],
      ["doc.json", wrench.saveJsonFile, wrench.loadJsonFile],
    ] as const) {
      const path = `${dir}/${name}`;
      save(TREE, path, ANY, wrench.LOCAL_FILE);
      assert.deepEqual(
        load(path, ANY, wrench.LOCAL_FILE),
        TREE,
        `${name} did not round trip`,
      );
    }
  });
});

// COVERS: FR-4.6 | property
void test("json canonical form is two-space indent, sorted, with a trailing newline", () => {
  const written = text(
    wrench.JSON.encode({ b: [1, { d: 4, c: 3 }], a: "x", e: null }),
  );
  assert.deepEqual(
    written,
    '{\n  "a": "x",\n  "b": [\n    1,\n    {\n      "c": 3,\n      "d": 4\n    }\n  ],\n  "e": null\n}\n',
  );
});

// COVERS: FR-4.6 | edge
void test("json canonical form keeps a non-ascii character as itself", () => {
  // `deno fmt` leaves it alone and the other packs write it, so escaping it
  // here would put this pack alone on the other side.
  const subject = { k: "café 日本語 🔧" };
  assert.deepEqual(
    text(wrench.JSON.encode(subject)),
    '{\n  "k": "café 日本語 🔧"\n}\n',
  );
  assert.deepEqual(wrench.JSON.decode(wrench.JSON.encode(subject)), subject);
});

// COVERS: FR-4.8 | property
void test("a float is positional and never an exponent", () => {
  const table: [number, string][] = [
    [1.2, "1.2"],
    [1e20, "100000000000000000000.0"],
    [1e-7, "0.0000001"],
    [-0, "-0.0"],
    [0.1, "0.1"],
    [3.141592653589793, "3.141592653589793"],
    [-2.5, "-2.5"],
    [1e6, "1000000.0"],
    [1e-5, "0.00001"],
    [48.0, "48.0"],
  ];
  for (const [value, want] of table) {
    assert.deepEqual(
      wrench.canonicalFloatText(value),
      want,
      `spelling ${value}`,
    );
  }
  // The two ends of the range, by length because the strings are 326 and 311
  // characters. Both agree with the Python pack, measured.
  assert.deepEqual(wrench.canonicalFloatText(5e-324).length, 326);
  assert.deepEqual(
    wrench.canonicalFloatText(1.7976931348623157e308).length,
    311,
  );
  for (const value of [5e-324, 1.7976931348623157e308]) {
    assert.deepEqual(
      Number(wrench.canonicalFloatText(value)),
      value,
      "the spelling does not read back",
    );
  }
});

// COVERS: FR-4.8 | negative
void test("a float with no canonical form is refused", () => {
  for (const value of [NaN, Infinity, -Infinity]) {
    assertThrows(() => wrench.canonicalFloatText(value), RangeError);
    assertThrows(() => wrench.canonicalNumberText(value), RangeError);
  }
});

// COVERS: FR-4.9 | property
void test("a control character is escaped and never written raw", () => {
  // A raw control character is refused by a strict reader and folded by a
  // lenient one, so escaping is the only answer that keeps every value
  // writable. U+0085, U+2028 and U+2029 are line breaks to a YAML 1.1 reader,
  // which is why they are on this list and U+200B is not: that is a printable
  // character and no pack escapes it.
  const points = [
    ...Array.from({ length: 0x20 }, (_, i) => i),
    0x7f,
    0x85,
    0xa0,
    0x2028,
    0x2029,
    0xfeff,
  ];
  const subject = Object.fromEntries(
    points.map((cp) => [
      `cp${cp.toString(16).padStart(4, "0")}`,
      `a${String.fromCodePoint(cp)}b`,
    ]),
  );
  const written = text(wrench.YAML.encode(subject));
  for (const cp of points) {
    // U+000A is checked by counting lines rather than by looking for it: it is
    // also the separator between one key and the next, so its presence says
    // nothing and only an extra line would.
    if (cp === 0x0a) continue;
    assert(
      !written.includes(String.fromCodePoint(cp)),
      `U+${cp.toString(16).padStart(4, "0").toUpperCase()} was written raw`,
    );
  }
  assert.deepEqual(
    written.split("\n").length - 1,
    points.length,
    "a value was written across more than one line, so a break was written raw",
  );
  assert.deepEqual(wrench.YAML.decode(written), subject);
  // JSON escapes fewer of them and that is JSON's own table, which is the part
  // of the library every pack found correct. What has to hold is the round
  // trip.
  assert.deepEqual(wrench.JSON.decode(wrench.JSON.encode(subject)), subject);
});

// COVERS: FR-4.10 | property
void test("an integer past the exact range widens to a float, visibly", () => {
  // The widening is deliberately VISIBLE: a number that cannot be carried
  // exactly is written with a `.0` rather than as a different exact-looking
  // integer, so a reader sees the precision go.
  //
  // JavaScript's exact range is 2^53 and not 2^63, because its one number type
  // is a double. The rule is the contract's and the boundary is the language's,
  // and the two int64 endpoints are where this pack diverges from the other
  // four. Measured against the Python pack.
  const table: [number, string][] = [
    [1, "1"],
    [2147483647, "2147483647"],
    [Number.MAX_SAFE_INTEGER, "9007199254740991"],
    [Number.MAX_SAFE_INTEGER + 1, "9007199254740992.0"],
    [1e20, "100000000000000000000.0"],
    // The uint64 endpoint arrives as text and not as a literal, and that is
    // what the requirement is about: the digits come off a file, the runtime
    // rounds them on the way in, and the spelling has to show that it did.
    // Written as a literal it is the same double to the bit, checked as
    // `Object.is` and as the raw bytes `000000000000f043` either way, so this
    // asserts what it asserted before against the value the decode below gets.
    [Number("18446744073709551615"), "18446744073709552000.0"],
  ];
  for (const [value, want] of table) {
    assert.deepEqual(
      wrench.canonicalNumberText(value),
      want,
      `spelling ${value}`,
    );
  }
  const decoded = wrench.YAML.decode("n: 18446744073709551615\n") as {
    n: number;
  };
  assert.deepEqual(
    text(wrench.YAML.encode(decoded)),
    '"n": 18446744073709552000.0\n',
  );
});

// COVERS: FR-4.11 | edge
void test("negative zero is a value in json and a spelling elsewhere", () => {
  // JavaScript decides what a JSON document means, and V8 reads `-0` as signed.
  // In YAML an integer zero cannot carry the sign, so `-0` is the integer 0 and
  // only `-0.0` is a signed zero. The decimal point is the whole distinction.
  assert(
    Object.is((wrench.JSON.decode('{"n": -0}') as { n: number }).n, -0),
    "JSON lost the sign",
  );
  assert(
    !Object.is((wrench.YAML.decode("n: -0\n") as { n: number }).n, -0),
    "YAML kept a sign on an integer zero",
  );
  assert(
    Object.is((wrench.YAML.decode("n: -0.0\n") as { n: number }).n, -0),
    "YAML lost the sign on -0.0",
  );
  // And it survives being written, which needs the float spelling.
  assert.deepEqual(text(wrench.YAML.encode({ n: -0 })), '"n": -0.0\n');
  assert.deepEqual(text(wrench.JSON.encode({ n: -0 })), '{\n  "n": -0.0\n}\n');
});

// ---- the packs --------------------------------------------------------------

// COVERS: FR-5.2 | property
void test("the pack binds an established validator rather than implementing one", () => {
  // The binding is asked something only a real JSON Schema implementation
  // answers: a 2020-12 keyword, applied to a document that violates it.
  const schema = wrench.compileSchema("2020-12 only", {
    $schema: "https://json-schema.org/draft/2020-12/schema",
    type: "object",
    properties: { a: { type: "integer" } },
    unevaluatedProperties: false,
  });
  schema.validate({ a: 1 });
  assertThrows(() => schema.validate({ a: 1, b: 2 }), wrench.ValidationError);

  const tuple = wrench.compileSchema("prefixItems", {
    $schema: "https://json-schema.org/draft/2020-12/schema",
    type: "array",
    prefixItems: [{ type: "string" }, { type: "integer" }],
    items: false,
  });
  tuple.validate(["a", 1]);
  assertThrows(() => tuple.validate(["a", "b"]), wrench.ValidationError);
});

// COVERS: FR-5.5 | property
void test("the shared fixture set decodes to one structure", async () => {
  // Packs agree on structure and no longer on bytes, so what a fixture holds is
  // a structure that must survive every pack: the input and the canonical form
  // beside it decode to the same thing here.
  let checked = 0;
  const entries = await readdir(new URL("testdata/canonical/", ROOT), {
    withFileTypes: true,
  });
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const base = new URL(`testdata/canonical/${entry.name}/`, ROOT);
    const input = wrench.YAML.decode(
      await readFile(new URL("input.yaml", base)),
    );
    const canonical = wrench.YAML.decode(
      await readFile(new URL("canonical.yaml", base)),
    );
    assert.deepEqual(
      input,
      canonical,
      `${entry.name}: the input and the canonical form differ`,
    );
    checked += 1;
  }
  assert(checked > 0, "the fixture set is empty, so this asserts nothing");
});

// COVERS: FR-5.6 | property
void test("the fixture set lives beside the schemas and this pack reads that copy", async () => {
  const fixtures = await stat(new URL("testdata/canonical", ROOT));
  assert(
    fixtures.isDirectory(),
    "testdata/canonical is not where the fixture set lives",
  );
  const schemas = await stat(new URL("schemas", ROOT));
  assert(schemas.isDirectory(), "schemas/ is not beside it");
});

// COVERS: FR-5.7 | positive
void test("the shipped set is reachable without the suffix", () => {
  // `schemas.JIG` rather than a name carrying `_SCHEMA`, the namespace carrying
  // what kind of thing these are so the names do not have to.
  for (const short of ["ENVELOPE", "JIG", "MANIFEST", "DEFINITIONS"]) {
    const schema = wrench.schemas[short];
    assert(
      schema instanceof wrench.CompiledSchema,
      `schemas.${short} is not a schema`,
    );
    assert(
      schema.name.startsWith("https://"),
      `schemas.${short} is not named by its $id`,
    );
  }
  // It validates, so the namespace carries working schemas and not just names.
  wrench.loadFormattedFile(
    "out.yaml",
    wrench.schemas.ENVELOPE,
    wrench.YAML,
    new Reading(VALID_ENVELOPE),
  );
});

// ---- reaching the library ---------------------------------------------------

// COVERS: FR-6.3 | positive
void test("a write replaces the previous contents whole", () => {
  withDirectory((dir) => {
    const path = `${dir}/out.yaml`;
    writeFileSync(path, "previous\n");
    wrench.LOCAL_FILE.write(path, new TextEncoder().encode("next\n"));
    assert.deepEqual(readFileSync(path, "utf8"), "next\n");
    assert.deepEqual(
      readdirSync(dir),
      ["out.yaml"],
      "a temporary was left behind",
    );
  });
});

// COVERS: FR-6.3 | property
void test("two writes leave the last one and no litter", () => {
  withDirectory((dir) => {
    const path = `${dir}/doc.yaml`;
    wrench.saveYamlFile({ a: 1 }, path, ANY, wrench.LOCAL_FILE);
    wrench.saveYamlFile({ b: 2 }, path, ANY, wrench.LOCAL_FILE);
    assert.deepEqual(wrench.loadYamlFile(path, ANY, wrench.LOCAL_FILE), {
      b: 2,
    });
    assert.deepEqual(readdirSync(dir), ["doc.yaml"]);
  });
});

// COVERS: FR-6.3 | edge
void test("a written file is readable by its consumers", () => {
  // A file created for a rename is owner-only, and evidence meant to be handed
  // around has to survive being handed around.
  withDirectory((dir) => {
    const path = `${dir}/out.yaml`;
    wrench.LOCAL_FILE.write(path, new TextEncoder().encode("success: true\n"));
    assert.deepEqual(statSync(path).mode & 0o777, 0o644);
  });
});

// COVERS: FR-6.3 | negative
void test("a failed write leaves no temporary behind", () => {
  // The temporary is what atomicity is built on, so a write that fails must not
  // leave one for somebody to find.
  withDirectory((dir) => {
    const notADirectory = `${dir}/file`;
    writeFileSync(notADirectory, "");
    const failure = assertThrows(
      () =>
        wrench.LOCAL_FILE.write(
          `${notADirectory}/out.yaml`,
          new TextEncoder().encode("x\n"),
        ),
      wrench.WriteError,
    );
    assert.deepEqual(failure.step, "write");
    assert.deepEqual(readdirSync(dir), ["file"]);
  });
});
