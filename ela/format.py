"""Number formatting for people: the CLI and the CSV export.

Python's `round` and `:.2f` work on the binary value of a float, so 76.625 prints as 76.62. The
project rules that 76.625 shows as 76.63. `format_pct` rounds half up on the shortest decimal
representation of the float instead. Negative numbers use the ASCII hyphen-minus.
"""

from decimal import ROUND_HALF_UP, Context, Decimal

NULL_TEXT = "—"  # em dash, shown for a value that does not apply
EVERY_DIGIT = Context(prec=400)  # the largest float has 309 digits before the point


def round_half_up(value: float, places: int = 2) -> Decimal:
    """`value` rounded half up at `places` decimals, taken from the shortest repr of the float."""
    return Decimal(repr(float(value))).quantize(
        Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP, context=EVERY_DIGIT
    )


def format_pct(value, places: int = 2) -> str:
    """A number with at most `places` decimals and no trailing zeros, or `—` for None.

    12.0 gives "12", 76.625 gives "76.63", -46.666667 gives "-46.67".
    """
    if value is None:
        return NULL_TEXT
    rounded = round_half_up(value, places)
    if rounded == 0:
        return "0"
    return format(rounded.normalize(), "f")
