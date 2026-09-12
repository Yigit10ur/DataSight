import numpy as np
import pandas as pd


def numeric_values(series: pd.Series) -> pd.Series:
    """Read a column as numbers, with anything unusable turned into a gap.

    Infinity is not a measurement: it cannot be averaged, binned or plotted, and
    pandas produces it from a literal "inf" in a CSV. Treating it as missing keeps
    one unreadable cell from taking down the statistics of the whole column.
    """
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
