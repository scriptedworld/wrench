// Asks the TypeScript pack whether each file is a valid schema.
//
//     node driver.ts FILE...
//
// One line per file, `ok NAME` or `INVALID NAME: reason`, which is what
// bin/test-schema-validity.py reads. The exit status is not what it reads.
import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { compileSchema } from "../../../typescript/src/mod.ts";

let refused = 0;
for (const path of process.argv.slice(2)) {
  const name = basename(path);
  try {
    compileSchema(name, readFileSync(path, "utf8"));
    console.log(`ok ${name}`);
  } catch (error) {
    refused++;
    console.log(`INVALID ${name}: ${String((error as Error).message).split("\n")[0]}`);
  }
}
process.exit(refused > 0 ? 1 : 0);
