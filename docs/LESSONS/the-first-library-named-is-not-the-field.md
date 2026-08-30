# The first library named is not the field, and stars do not rank it

## What happened

FACT 2026-08-30. Sizing a Zig pack needed a JSON Schema validator, a YAML codec
and a TOML codec. Each was chosen the same way: GitHub search on one or two
terms, sorted by stars, top few taken.

**That method missed the better answer three times, and all three better answers
came from our user naming them.**

    validator   sized against WhiskeyTuesday/zig-jsonschema, 2 stars, carried
                over from a previous session and never compared against
                anything. h0rv/jsonschema.zig, 1 star, resolves 10 of 10
                reference forms against its 1 of 10, compiles all four shipped
                schemas against its 3, has no dependencies, and passes the whole
                official suite with nothing skipped against its 305 skips.

    YAML        chosen kubkon/zig-yaml, 295 stars, which cannot tell `123` from
                `"123"` and accepts 3 of 21 escapes. cloudboss/yaml-zig appears
                in NO search run that day: standards-compliant YAML 1.2, an API
                shaped like std.json's, 21 of 21 escapes, and it vendors and
                passes the official YAML test suite, 402/402.

    JSON        two simdjson ports were offered and both were rejected on
                measurement, so the standard library held. That one worked.

## What it cost

A fortnight of reference-resolution work was designed, sized and written up
against a validator that was never compared to anything. The whole item
evaporated when the field was actually surveyed: our user's ruling to support
every reference form turned out to cost nothing, because a library already did.

## The general shape

**Popularity is not a quality signal in a young ecosystem, and it inverts.** The
two libraries finally chosen have one star each. The two with the most stars in
their categories, 295 and 132, were both rejected on measurement. The top-ranked
result for `jsonschema language:zig` is four stars and four years stale.

**A carried-over choice is not a choice.** The validator arrived from a previous
session's notes and was treated as settled. Nothing marked it as unexamined,
because a note that names one option looks the same as a note that compared
several.

## What to do instead

**Survey before sizing, and it costs two commands.**

    gh api -X GET search/repositories -f q='<topic> language:<lang>' \
        -f sort=updated -f per_page=10 \
        --jq '.items[] | "\(.stargazers_count)\t\(.full_name)\t\(.license.spdx_id)\t\(.pushed_at[0:10])"'

**Sort by recency, not stars.** Sorting by `updated` surfaced a dozen libraries
the star-sorted search hid. Search several phrasings; the names collide badly,
and `zig-yaml`, `yaml-zig` and `zig_yaml` are different projects by different
authors.

**Rank on two questions that are each one command.** Both separated every case
here where popularity separated none:

    does it build on the compiler you actually have
    does it vendor and pass the official test suite for what it claims

Thirteen libraries were built that day. Six build and pass their own suite,
three have a working library behind a broken harness, three do not compile at
all. No ranking predicted which.

**Name the remote and the commit in any claim about a library**, because the
names collide and a bare name is ambiguous.

## What does not help

**Reading the README's headline number.** One validator's README says 99.9%,
which is true and is a proportion of what it chose to run. Against the whole
official suite it is 1190 of 1496, with 305 groups skipped on unsupported
keywords and refs, and the skipped set is exactly where wrench lives. Run the
suite and read the runner: the one that counts an unindexable schema as *failed*
is telling the truth, the one that skips it is not.
