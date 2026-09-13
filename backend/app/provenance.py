from pydantic import BaseModel


class Provenance(BaseModel):
    """What shaping did to the meaning of a dataset's rows.

    Not how far the data has come, but what has to be said about it. A filter leaves
    a row meaning what it meant; an aggregate does not, and a finding that treats a
    group total as an observation is answering a different question from the one the
    reader thinks they asked. Filling or dropping gaps is the same problem on the
    quality side: the score then describes the recipe as much as the data.

    Everything here is read off a recipe, so an uploaded file carries the default —
    nothing was shaped, and nothing needs saying.
    """

    steps: int = 0
    # An aggregate is somewhere in the chain, so a row is a group of the file rather
    # than one of its records.
    rows_are_groups: bool = False
    # The recipe filled or dropped gaps, so completeness measures the recipe.
    gaps_were_shaped: bool = False
    # Rows were taken out, so what is scored is what is left rather than the file.
    rows_were_removed: bool = False


GROUPED_ROWS_CAVEAT = (
    "Each row here is a group summarised from the file it came from, not one of its "
    "records, so this describes the groups and not what is inside them."
)
