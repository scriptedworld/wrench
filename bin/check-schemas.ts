// Check the shipped schemas with an implementation that is not wrench's.
//
//     deno run --allow-read --allow-net bin/check-schemas.ts
//
// WHY THIS EXISTS. Both packs compile their own schemas, which cannot catch both
// bindings misreading the specification the same way. Nothing outside wrench had
// ever read these files. ajv is neither Go's santhosh-tekuri nor Python's
// jsonschema, so it is a second opinion.
//
// WHY A SCRIPT RATHER THAN ajv-cli. The library is first class: 377 million
// downloads a week and released 2026-04-24, measured 2026-08-27. Its CLI is not:
// ajv-cli 5.0.0 was last released 2023-04-28, over three years earlier. A gate
// task should not depend on an unmaintained wrapper when the wrapper is fifteen
// lines, so wrench keeps the fifteen lines and binds the maintained library.
//
// Run through deno, which is installed and declared, so this needs no global npm
// install and no package.json in a repository with no other JavaScript. deno
// caches the package, so only a cold cache reaches the network.
import Ajv2020 from "npm:ajv@8/dist/2020.js";

const SCHEMA_DIR = "schemas";

// strict: false because wrench's schemas use union types deliberately, and ajv's
// strict mode is a style opinion rather than a validity check. allErrors so one
// run reports every problem instead of the first.
const ajv = new Ajv2020({ strict: false, allErrors: true });

const documents = new Map<string, { $id?: string }>();
for await (const entry of Deno.readDir(SCHEMA_DIR)) {
  if (!entry.name.endsWith(".schema.json")) continue;
  const document = JSON.parse(await Deno.readTextFile(`${SCHEMA_DIR}/${entry.name}`));
  if (!document.$id) {
    console.error(`${entry.name}: declares no $id, so nothing can reference it`);
    Deno.exit(1);
  }
  documents.set(entry.name, document);
}

if (documents.size === 0) {
  console.error(`${SCHEMA_DIR} holds no schemas, so this check asserts nothing`);
  Deno.exit(1);
}

let failures = 0;

// Register every schema before compiling any, so a $ref between two of them
// resolves from the shipped set rather than reaching the network. Both packs do
// the same; FR-3.6.
//
// addSchema validates against the metaschema, so an invalid document fails HERE
// rather than at compile. Caught per schema: an uncaught throw would put a
// JavaScript stack trace into a bolt work directory, where the reason has to be
// legible to somebody reading evidence on another machine.
for (const [name, document] of [...documents].sort()) {
  try {
    ajv.addSchema(document);
  } catch (error) {
    failures++;
    documents.delete(name);
    console.log(`INVALID  ${name}: ${(error as Error).message}`);
  }
}

for (const [name, document] of [...documents].sort()) {
  try {
    ajv.getSchema(document.$id!) ?? ajv.compile(document);
    console.log(`ok       ${name}`);
  } catch (error) {
    failures++;
    console.log(`INVALID  ${name}: ${(error as Error).message}`);
  }
}

console.log(
  failures === 0
    ? `\n${documents.size} schema(s) valid 2020-12, checked by ajv.`
    : `\n${failures} schema(s) are not valid 2020-12.`,
);
Deno.exit(failures === 0 ? 0 : 1);
