/**
 * The formatter for this pack.
 *
 * PRETTIER, because Node ships no formatter and prettier is what the ecosystem
 * uses for this: it is the default in the TypeScript templates, in the editors
 * and in the CI examples, and a reviewer arriving cold needs no explanation of
 * what formatted the tree. `deno fmt` did this job while the pack was
 * Deno-first, and it is not available to a consumer who installs from npm.
 *
 * A JavaScript config rather than `.prettierrc.json`, so the reasoning can sit
 * beside the settings. prettier reads either.
 *
 * Almost nothing is set. Prettier's whole argument is that the options are not
 * worth arguing about, and its defaults already match what the tree was
 * formatted to: 80 columns, two spaces, double quotes, semicolons, trailing
 * commas. Adding settings here would be re-litigating that for no gain.
 *
 * @type {import("prettier").Config}
 */
export default {};
