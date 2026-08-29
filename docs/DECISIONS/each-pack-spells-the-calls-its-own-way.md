# Each pack spells the two calls the way its own language spells things

## The decision

The contract names the calls `load_formatted_file` and `save_formatted_file`.

    Go        LoadFormattedFile   SaveFormattedFile
    Python    load_formatted_file save_formatted_file

The Go pack exports the exported-identifier form because that is how Go spells
an exported function. Python matches the contract because that is how Python
spells a function.

## Why

**What the packs share is behaviour, not identifiers.** A pack that spelled its
calls in another language's convention would be a foreign object in every codebase
that used it, and the cost lands on every call site rather than once here.

## Why it is written down

So that the next pack does not read the Go one, see `LoadFormattedFile`, and
conclude the names drifted from the contract. They did not: the contract is
`load_formatted_file` and Go is spelling it.

This matters most for the packs not yet built.

    Rust        load_formatted_file  save_formatted_file
    Ruby        load_formatted_file  save_formatted_file
    TypeScript  loadFormattedFile    saveFormattedFile

Rust and Ruby spell functions in snake case, so both match the contract directly.
**TypeScript does not**, and camel case is what its ecosystem expects, so it
transforms the contract exactly as Go does. Two of the four planned packs
therefore rename, which is the rule working rather than an exception to it.

## A pack may widen an argument's type to its language's idiom

Go and Rust take a path as a string because neither has anything else. Python
takes `str | os.PathLike[str]`, which is what `open()` takes and what a caller
expects of a path parameter.

That is the same rule as the naming, applied to a type: what the packs share is
behaviour, and a `pathlib.Path` has always worked here because every path
reaches the shipped IO through `Path(path)`. Annotating the parameter `str`
reported four errors in the first consumer to type-check against the pack, on
calls that run correctly, which is an annotation narrower than the contract
rather than a contract the consumer broke.

Widening the surface does not widen the seams. A path is normalised once on the
way in, so a `Reader` or `Writer` is handed one type and an error message quotes
one spelling. A value that is neither raises `usage`, because the call was made
wrongly before any file was touched; reaching the reader it would surface as
`read` and blame the filesystem.

The limit is that widening must not change what the packs agree on. A type a
caller passes is that caller's convenience, and a type wrench hands back is the
contract, which FR-2.9 fixes for every pack.

## What does not vary

The argument order and meaning are the contract, and no pack reorders them:

    load(path, schema, codec, reader)
    save(data, path, schema, codec, writer)

The schema is a required argument in every pack, and a pack that lets it default
has broken FR-2.2 whatever it calls the function.
