# Every error crossing the boundary is a wrench error

**Decided 2026-08-28.** Whatever a bound library raises, a caller of wrench sees
a wrench error. The cause is preserved and reachable; what does not cross the
boundary is a type the caller has to know a dependency to name.

## Why

A consumer writing `except wrench.ValidationError` or `errors.As(&wrench.ParseError{})`
should not have to know that wrench binds PyYAML rather than ruamel, or
santhosh-tekuri rather than another validator. **If the bound library is visible
in the error type, it is part of the contract**, and swapping it becomes a
breaking change for every consumer rather than an implementation detail.

It is the same failure as the float defect one layer up: a library's choice
escaping into what wrench promises.

## The measured surface, 2026-08-28

**The two calls wrap correctly. Everything beneath them leaks.** A consumer using
`load_formatted_file` is already fine; a consumer using a codec, a schema or
`compile_schema` directly is not.

Python, 9 of 15 entry points:

    compile_schema, not JSON     json.decoder.JSONDecodeError
    compile_schema, bad schema   jsonschema.exceptions.SchemaError
    Schema.validate, refused     builtins.ValueError
    YAML.decode, malformed       yaml.parser.ParserError
    JSON.decode, malformed       json.decoder.JSONDecodeError
    TOML.decode, malformed       tomllib.TOMLDecodeError
    the three encode failures    builtins.ValueError

Go, 7 of 11:

    Schema.Validate, refused     santhosh-tekuri/jsonschema/v6.ValidationError
    JSON.Decode, malformed       encoding/json.SyntaxError
    TOML.Decode, malformed       BurntSushi/toml.ParseError
    the rest                     fmt.wrapError, errors.errorString

Rust: `Codec::decode` and `Schema::validate` return
`Box<dyn Error + Send + Sync>`, and `serde_json::from_slice(data)?` puts
serde_json's own error straight into the box. The `Error` enum exists and the two
calls use it; the traits beneath do not.

## The rule

1. **Every public entry point returns wrench's own error type.** Not only the two
   calls. A codec, a schema, an IO boundary and `compile_schema` are all public,
   so all of them are boundaries.
2. **The cause is preserved, never swallowed.** Python `raise ... from err`, Go
   `%w`, Rust `#[source]`. A caller who genuinely wants the underlying type can
   still reach it; what changes is that they must ask rather than be handed it.
3. **The message names the step.** FR-2.6's distinction — parse against validate
   — extends downward rather than stopping at the two calls.

## What it costs, stated rather than discovered

**Python is the one that can break somebody.** `except yaml.ParserError` around a
direct `YAML.decode` stops catching once the wrap lands, and no base-class trick
fixes that without inheriting from every library's exception. The documented API
is the two calls, which already wrap, and the pack is 0.1.0; that is the argument
for doing it now rather than after a consumer depends on it.

**Go is compatible.** Wrapping with `%w` keeps `errors.Is` and `errors.As`
working against the underlying type, so a consumer doing either keeps working
and gains the wrench type.

**Rust is a signature change.** Returning `Error` rather than
`Box<dyn Error + Send + Sync>` from the traits is what makes the guarantee real,
and it is the change a consumer notices at compile time rather than at runtime,
which is the better of the two.

## What this is not

**Not hiding the cause.** A wrapped error that discards what happened is worse
than a leaked one: the leak at least says what went wrong. Every wrap carries its
source, and the tests assert the source is reachable.

**Not a reason to invent an error per library.** The set stays the one FR-2.6
implies — read, parse, validate, encode, write — plus whatever `compile_schema`
needs, which is the one genuinely open question, recorded in
`clank/tasks/wrench/parity/60`.
