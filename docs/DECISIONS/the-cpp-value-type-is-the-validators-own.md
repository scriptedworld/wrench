# The C++ value type is the validator's own

## The decision

`wrench::value` is an alias for `jsoncons::json`. The C++ pack does not own a
variant tree of its own, and the alias is honest about whose type it is.

    namespace wrench { using value = jsoncons::json; }

This is the one place a pack names a bound library's type on its own surface.
Every other pack hands back its language's single value type: `any` in Go,
`object` in Python, `serde_json::Value` in Rust, which is that crate's type for
the same reason this is jsoncons's.

## Why

C++ has no value type every parser and validator agrees on, and that is the whole
of it. A 2020-12 validator in this language brings its own document model and
validates that model: jsoncons validates `jsoncons::json`, blaze validates
`sourcemeta::core::JSON`. valijson is the adapter-shaped exception and implements
draft 7, which `which-libraries-the-cpp-pack-binds` refuses for the dialect.

FR-2.2 compels a schema, so every load validates, so every loaded value reaches
the validator's type. A tree the pack owned would be converted into that type on
the way in and out of it on the way back, on every call, to arrive at the same
values. The conversion buys a name.

Two more things come free, and neither is the reason but both would be work
otherwise. `jsoncons::json` keeps its members ordered by key, so the first of the
four adapters is a property of the type and no sorting code exists. And its model
is exactly FR-2.9's: maps, lists, string, number, boolean, null, with a string
for every key.

## What it costs

**A consumer's call sites name the library.** Binding a different validator later
is a breaking change to every consumer, not an internal one. That is the trade,
and it is accepted because the alternative buys a rename and pays a conversion.

**The library's model is wider than the contract's**, so the codecs refuse the
parts that are not in it. jsoncons carries big numbers, byte strings, dates and
regular expressions as tagged values, and a string tagged as a decimal is written
unquoted: a caller handing one to `encode` would put arbitrary text into the
output. Both codecs therefore refuse a string carrying any tag but `none` and the
`noesc` its own parser sets, with an `encode` failure naming the value.

**The pack's public headers include jsoncons.** A consumer compiles against them,
which is a compile-time cost on every translation unit that names a value, and it
is why the pack's CMake makes jsoncons a public dependency and a system include
directory.

## What was measured

Three differences between what jsoncons produces and what the contract states,
each settled inside the codecs:

- Above the signed 64-bit maximum it keeps an exact `uint64`, where FR-4.10 says
  the value widens to a float visibly. The pack widens after decoding. Further
  out, `lossless_bignum(false)` has the library widen for it.
- Its own float spelling is not FR-4.8's, and it writes `-0.0` as `0.0`. Every
  float is respelled by `canonical_float` before the library sees it, handed back
  as a decimal string tagged `bigdec`, which it writes bare. The output is then
  the pack's spelling in every case.
- A `-0` integer token decodes to a signed zero in JSON (FR-4.11) and jsoncons
  cannot say so: `end_negative_value` in its parser converts an integer token
  before the lossless path sees it, so `-0` and `0` arrive identical. The JSON
  codec respells that one token as `-0.0` in the bytes before the parse, which is
  the only place either codec touches its input.
