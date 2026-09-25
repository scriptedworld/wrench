# A C++ failure is a returned value, and `usage` does not exist there

## The decision

Every entry point in the C++ pack answers with `std::expected<T, failure>`, and
`failure` carries the step, a message and an operating system code where there was
one. Nothing the pack does throws on purpose.

    [[nodiscard]] result<value> load_formatted_file(path, schema, codec, reader);

Six kinds ship: `read`, `parse`, `schema`, `validate`, `encode`, `write`. The
seventh, `usage`, is absent.

## Why a value and not an exception

A file that is not there, a document that will not parse and a value with no
canonical form are results a caller is expected to handle. They are what wrench is
for, and none of them is a fault in the program. Handing them back as values puts
the handling in the signature, where `[[nodiscard]]` makes ignoring one a warning
and `-Werror` makes it a failure of the build.

The kinds are one type and not a hierarchy, so FR-2.11's "nothing escapes the
family" is a property of the return type instead of a discipline about catch
blocks. A consumer switches on `step` or reads `message` and never links a bound
library's exception type.

Both bound libraries do throw, and the boundary is where that stops. jsoncons
throws `json_exception` on a bad document and `schema_error` from the resolver;
libyaml returns codes and sets `problem`. Each is caught or checked at the seam it
came from and becomes a `failure`.

## What still leaves through a throw

`std::bad_alloc`. Reporting an allocation failure means building a message, which
allocates, so the family cannot carry it. This is said in `error.hpp` rather than
hidden, and the suite's replacement `operator new` is what exercises the paths an
allocation failure takes.

## Why `usage` is absent

The seams arrive as references: `const schema&`, `const codec&`, `const reader&`,
`const writer&`. A call naming none of them does not compile, so there is no
run-time state for a `usage` failure to report. SPEC.md permits this for a
language with that property, and Rust omits the kind for the same reason with
`&dyn Schema`.

Go and Python keep the kind because both let an interface or a name be nil, which
is where FR-2.3's guarantee needs enforcing at run time.

## The cause travels as words

FR-2.11 asks that the cause be reachable, and in the three packs that throw it is
reachable as an object: `__cause__`, `errors.Unwrap`, `source()`. Here the cause
is in the message, and the `failure` carries a `std::error_code` only where a
system call produced one.

Carrying the exception itself, as a `std::exception_ptr`, was considered and
refused. A consumer could only use it by rethrowing and catching the bound
library's own type, which is the leak FR-2.11 exists to close. What a consumer
needs is the kind to match on and the words to read, and both are there.

## The message shapes

A reader and a writer are handed the path, so they name the file themselves. A
codec is handed bytes and a schema a structure, so neither knows which file it is
working on, and the two calls fill it in:

    reading /p/x.yaml: No such file or directory
    parsing /p/x.yaml: did not find expected key at line 2 column 1
    validating /p/x.yaml: /version: String does not match pattern
    the schema for /p/x.yaml: no schema was compiled
    encoding /p/x.yaml: a NaN has no canonical form
    writing /p/x.yaml: No such file or directory

FR-3.10d's refusal is the exception that proves the rule: it is produced by
`schema::compile`, outside the two calls, so it reaches a caller as the one
sentence the contract fixes with nothing added to it.
