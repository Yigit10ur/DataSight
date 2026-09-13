from collections.abc import Iterable

from app.provenance import Provenance
from app.recipes.models import Recipe

# Steps that change what a row is, or what the quality report can find in one.
GROUPING_OPS = {"aggregate"}
GAP_OPS = {"fill_missing", "drop_missing"}
ROW_REMOVING_OPS = {"filter_rows", "limit_rows", "drop_missing", "drop_duplicates", "aggregate"}


def provenance_of(recipes: Iterable[Recipe]) -> Provenance:
    """Read a chain of recipes for what has to be said about what they produced."""
    ops = [step.op for recipe in recipes for step in recipe.steps]

    return Provenance(
        steps=len(ops),
        rows_are_groups=any(op in GROUPING_OPS for op in ops),
        gaps_were_shaped=any(op in GAP_OPS for op in ops),
        rows_were_removed=any(op in ROW_REMOVING_OPS for op in ops),
    )
