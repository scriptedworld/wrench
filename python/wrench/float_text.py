"""The one spelling of a float, shared by all three of this pack's codecs.

FR-4.8. Positional decimal, never an exponent. The digits are the shortest
decimal string that reads back as the same float, placed with the decimal point
where it belongs rather than moved into an `e`. A whole number keeps a ``.0``,
so a float never reads back as an integer.

The rule carries no threshold on purpose. Every alternative needs a magnitude at
which the spelling changes, and that number then has to be stated in the
contract and implemented identically in nine places. "Never" is the only answer
with nothing to get wrong, and the only one a consumer parsing with a naive
numeric pattern reads correctly: ``1e+06`` matched by ``[0-9.]+`` yields 1,
which is how this defect was found.

The cost is bounded: 326 characters for a subnormal near the bottom of the
range, 311 for the largest finite double.
"""

from __future__ import annotations

import math
from decimal import Decimal


def canonical_float_text(value: float) -> str:
    """The canonical spelling of one float.

    ``repr`` gives the shortest round-tripping digits and chooses an exponent on
    a threshold of its own. ``Decimal`` of that repr is exact, and formatting it
    with ``f`` places the point positionally without touching the digits, so the
    round trip is repr's and only the placement is wrench's.

    NaN and the infinities are refused. YAML can spell them, JSON Schema cannot
    represent them, and a file no consumer in this ecosystem can validate is not
    canonical form.
    """
    if math.isnan(value) or math.isinf(value):
        raise ValueError(f"cannot write {value} in canonical form")
    text = format(Decimal(repr(value)), "f")
    return text if "." in text else text + ".0"
