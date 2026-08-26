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

    Ruby      load_formatted_file  save_formatted_file
    Rust      load_formatted_file  save_formatted_file

Both of those languages spell functions in snake case, so both match the contract
directly and Go stays the only one that transforms it.

## What does not vary

The argument order and meaning are the contract, and no pack reorders them:

    load(path, schema, codec, reader)
    save(data, path, schema, codec, writer)

The schema is a required argument in every pack, and a pack that lets it default
has broken FR-2.2 whatever it calls the function.
