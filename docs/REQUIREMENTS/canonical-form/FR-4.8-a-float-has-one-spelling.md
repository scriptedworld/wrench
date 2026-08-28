# FR-4.8

| ID | Requirement | |
|---|---|---|
| FR-4.8 | A float is written in positional decimal notation and never in exponent notation, in every codec and every pack. The digits are the shortest decimal string that reads back as the same double, placed with the decimal point where it belongs. A whole number keeps a trailing `.0`, and a negative zero keeps its sign. NaN and the infinities are refused. | |

The rule carries no threshold, and that is the requirement rather than an
implementation note. Every alternative spelling needs a magnitude at which the
form changes, which then has to be stated here as a number and implemented
identically in nine places; "never" has nothing to get wrong.

It is also the only spelling a consumer parsing with a naive numeric pattern
reads correctly. `1e+06` matched against `[0-9.]+` yields `1`, which is how this
was found: a count of a million displayed as one, across a repository boundary,
with no error anywhere.

The cost is bounded and is accepted. The longest output is 326 characters, for a
subnormal near the bottom of the range, and the largest finite double is 311.

**This is a property of the value, not of the format.** YAML, JSON and TOML can
all spell an exponent, and all three are forbidden from doing so here, because a
consumer that reads a number out of one format and compares it against the same
number from another is the case the contract exists to serve.
