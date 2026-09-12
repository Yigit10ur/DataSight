def number(value: float) -> str:
    """Render a measured value the way a reader would write it.

    Whole numbers keep no decimals, small numbers keep two, and thousands are
    grouped. The point is that the string stays a faithful rendering of the metric
    it came from, so a reader can find it again in the structured output.
    """
    if value == int(value) and abs(value) < 1e15:
        return f"{int(value):,}"
    if abs(value) >= 100:
        return f"{value:,.1f}"
    return f"{value:,.2f}"


def percent(ratio: float) -> str:
    return f"{ratio:.1%}"


def multiple(ratio: float) -> str:
    return f"{ratio:.1f}x"
