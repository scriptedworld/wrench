# FR-4.9

| ID | Requirement | |
|---|---|---|
| FR-4.9 | A control character in a string is escaped rather than written raw, using the escape table of the format being written. Every pack writes the same table for the same format, and no value is refused for carrying one. | |

**A raw control character is read differently by different readers.** A strict
YAML parser refuses the file, a lenient one accepts it, and one implementing the
YAML 1.1 line-break set folds some of them to a space with no error. So a file
carrying one has no single meaning, and the pack that wrote it cannot say what a
consumer will get.

**Escaping rather than refusing is what
`docs/DECISIONS/parity-is-reached-by-widening-never-by-refusing.md` requires.**
Every value stays writable; nothing is limited to make the packs agree.

**The table belongs to the format, not to the library.** YAML and TOML spell
escapes differently and neither is wrong; what must not differ is two packs
writing the same format two ways. YAML names fourteen points and uses `\xNN`
elsewhere; TOML has no `\e`, `\v`, `\0` or `\x`, so anything without a name
becomes `\uXXXX`.

**U+0085, U+2028 and U+2029 are escaped in YAML** even though nothing observable
misbehaves today. YAML 1.1 makes all three line breaks and 1.2 does not, so which
of them fold depends on the reader's version rather than on the character. The
three parsers reachable from here all preserve U+2028 and U+2029 and all fold
U+0085, which is a property of those implementations rather than of the format.

**C1 is left raw in TOML.** TOML does not require escaping it and every parser
round trips it, so escaping there would be a pack inventing a rule the format
does not have.
