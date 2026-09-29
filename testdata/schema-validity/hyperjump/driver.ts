// Asks @hyperjump/json-schema whether each file is a valid 2020-12 schema.
//
//     deno run --allow-read driver.ts FILE...
//
// This is the reader no pack binds, which is what keeps unanimity from becoming
// unanimity among wrench's own bindings. It validates each document against
// the 2020-12 meta-schema it bundles; run without --allow-net, it cannot fetch
// one.
//
// One line per file, `ok NAME` or `INVALID NAME: reason`, which is what
// bin/test-schema-validity.py reads. The exit status is not what it reads.
import { validate } from "npm:@hyperjump/json-schema@1.17.8/draft-2020-12";

const META = "https://json-schema.org/draft/2020-12/schema";

let refused = 0;
for (const path of Deno.args) {
  const name = path.split("/").pop() ?? path;
  const output = await validate(META, JSON.parse(await Deno.readTextFile(path)));
  if (output.valid) {
    console.log(`ok ${name}`);
  } else {
    refused++;
    console.log(`INVALID ${name}: not valid against the 2020-12 meta-schema`);
  }
}
Deno.exit(refused > 0 ? 1 : 0);
