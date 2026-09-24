/**
 * The linter for this pack.
 *
 * ESLINT with TYPESCRIPT-ESLINT, because Node ships no linter and this is the
 * pair the TypeScript ecosystem uses: eslint is the linter, and typescript-eslint
 * is how eslint is taught TypeScript. `deno lint` did this job while the pack
 * was Deno-first, and it is not available to a consumer who installs from npm.
 *
 * The type-aware rules are on, which is the whole reason to prefer this pair
 * over a syntax-only linter. `strictTypeChecked` reads the same type
 * information `tsc` does, so it catches a floating promise, an `any` leaking out
 * of a cast and a condition that is always true. None of those are visible to a
 * linter that only parses. It costs a type build per run, which for a pack this
 * size is under two seconds.
 *
 * `stylisticTypeChecked` is deliberately NOT on. It is a set of preferences
 * about how to spell things a type checker already settles, and this tree was
 * written to another formatter's preferences; adopting it would be a rewrite
 * wearing a linter's clothes rather than a check on the code.
 *
 * `eslint-config-prettier` is last and turns off the rules that argue with the
 * formatter. That is not a relaxed check: prettier owns layout, so a lint rule
 * about layout can only produce a fight between two tools over the same file.
 *
 * `src/shipped.ts` is generated and is linted anyway. The generator writes
 * ordinary exported constants, so there is nothing for a rule to object to, and
 * an exclusion would hide a future generator that emitted something worse.
 */

import eslint from "@eslint/js";
import prettier from "eslint-config-prettier";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    // Neither source nor this pack's: installed packages, and the outputs a
    // tool recreates.
    ignores: ["node_modules/**", "coverage/**", ".bolt-*/**"],
  },
  eslint.configs.recommended,
  {
    files: ["**/*.ts"],
    extends: [tseslint.configs.recommendedTypeChecked],
    languageOptions: {
      parserOptions: {
        // The project's own tsconfig, found for each file, so the rules see the
        // same types `npm run types` does rather than a second declaration of
        // what this project is.
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
  {
    // The config files are JavaScript and are outside tsconfig's `include`, so
    // the type-aware rules have no program to read them from.
    files: ["**/*.js"],
    extends: [tseslint.configs.disableTypeChecked],
  },
  prettier,
);
