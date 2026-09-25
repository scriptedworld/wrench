// The validate seam, and the schemas that ship.
//
// A schema applies to the decoded structure and never to the text (FR-3.3), so
// one schema judges a document whichever codec read it. It is handed a value and
// not a path, so it cannot name the file it is working on, and the two calls are
// what put the path into a failure.
//
// Two kinds of failure live here and the pair is the distinction most easily
// lost. `schema` means the schema itself could not be compiled or resolved, so
// nothing can be checked against it and the fix is to the schema. `validate`
// means the document did not match a schema that is fine, and the fix is to the
// document.
//
// A `$ref` reaches the document's own fragments or the shipped set and nothing
// else (FR-3.10). There is no argument, no environment variable and no build
// setting that widens it.
#pragma once

#include <memory>
#include <span>
#include <string_view>

#include "wrench/error.hpp"
#include "wrench/value.hpp"

namespace wrench {

// A compiled schema, held by value and cheap to copy.
//
// Compilation happens once, in `compile`, so a schema validating many documents
// pays for the schema once. A default-constructed one is compiled against
// nothing and refuses every document with a `schema` failure, which is what a
// caller gets from a shipped accessor if a shipped schema ever stopped
// compiling.
class schema {
   public:
    schema();

    // The schema the value describes, compiled, or why it could not be.
    //
    // `name` is the reference the document was retrieved under, and it matters
    // only where the document declares no `$id`: a relative `$ref` resolves
    // against the document's `$id` where there is one and against this name
    // where there is not (FR-3.10b). A document may not declare an `$id` a
    // shipped schema already declares, because a shipped schema is there to fix
    // what the envelope means and a caller's document does not get to decide it.
    //
    // A schema held as text rather than as a value reaches this through the JSON
    // codec, `json().decode(text)`, which keeps a malformed schema document
    // inside wrench's own family as a `parse` failure.
    [[nodiscard]] static result<schema> compile(const value& document,
                                                std::string_view name = {});

    // Whether the document matches. The failure names the location inside the
    // document and what was wrong there.
    [[nodiscard]] result<void> validate(const value& instance) const;

   private:
    struct state;

    schema(std::shared_ptr<const state> held, failure refusal);

    // Null until something compiles. The refusal is what `validate` answers with
    // while it is, so a schema is usable as a value without ever being a
    // pointer a caller has to check.
    std::shared_ptr<const state> held_;
    failure refusal_;
};

// The schemas that ship with the library (FR-3.2), discovered by reading the
// directory they live in and never from a list of filenames (FR-3.7).
namespace schemas {

// One shipped schema: the name of its file, the `$id` it declares, and the bytes
// the pack carries, which are the bytes in `schemas/` and not a copy of them.
struct entry {
    std::string_view stem;
    std::string_view id;
    std::string_view text;
};

// The whole shipped set, in the order the directory gave it.
//
// This is the authority on what the pack ships, and every pack answers to the
// same directory rather than to another pack (FR-5.7). The four accessors below
// are names for members of this set and not a second list of what the set holds:
// a schema added to `schemas/` arrives here with nothing in this pack edited,
// and the suite fails until it has an accessor and a fixture of its own.
[[nodiscard]] std::span<const entry> all();

// One shipped schema by the name of its file, compiled once.
//
// This is the whole of the discovery path: a schema added to `schemas/` is
// reachable here on the next build with nothing in this pack edited. A name the
// set does not hold answers with a schema that refuses every document, so the
// call is total and a typo is a refusal rather than a crash.
[[nodiscard]] const schema& by_stem(std::string_view stem);

[[nodiscard]] const schema& definitions();
[[nodiscard]] const schema& envelope();
[[nodiscard]] const schema& jig();
[[nodiscard]] const schema& manifest();

}  // namespace schemas

}  // namespace wrench
