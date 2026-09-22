# Example data

[orders-sample.csv](orders-sample.csv) is a synthetic sales extract written for the
walkthrough in the [project README](../README.md#walkthrough-with-the-example-data).
It is invented: no real customers, people, companies, or confidential figures. The
file is fixed rather than generated at run time, and every analysis DataSight runs
over it is deterministic, so the figures it reports never move.

60 rows and 9 columns, covering 19 months of orders from January 2024 to July 2025.

| Column | Type DataSight infers | What it holds |
| --- | --- | --- |
| `order_id` | text | `ORD-1001` upwards; 57 distinct values across 60 rows |
| `order_date` | datetime | Three orders a month, on the 8th, 17th, and 25th |
| `channel` | categorical | `Online`, `Retail`, `Partner` — and some dirty spellings |
| `region` | categorical | `North`, `South`, `East`, `West` |
| `units` | numeric | Items ordered, 7 to 19 |
| `unit_price` | numeric | 21.30 to 33.34 |
| `order_total` | numeric | `units` × `unit_price` |
| `delivery_days` | numeric | Usually 2–6 days, with gaps and a few very late deliveries |
| `discount_pct` | categorical | Percentages written as text, because four rows say `pending` |

## Planted quality issues

The file is deliberately imperfect, so the quality report has something to find. Each
of these produces one **warning**:

1. **Missing values.** `delivery_days` is empty in 7 of 60 rows (11.7%).
2. **Duplicate rows.** `ORD-1004`, `ORD-1023`, and `ORD-1045` each appear twice as
   byte-identical rows, the way a double import leaves them.
3. **Outliers.** Three deliveries took 19, 23, and 29 days against a median of 3.
4. **Categories that differ only in case or spacing.** `channel` holds `Online`,
   `online`, and `" Online"`, plus `Retail` and `"Retail "`.
5. **Whitespace.** Those seven padded `channel` values are also reported on their own,
   because stray spaces split a category silently.
6. **Numbers stored as text.** `discount_pct` is 93% numeric, but the four `pending`
   rows keep the whole column out of numeric analysis.

Alongside them the file carries genuine structure to analyse: `West` orders are
larger than `North` orders, `units` and `order_total` move together, and `units`
rises over the 19 months.

The README walkthrough names the exact figures DataSight reports. They are pinned by
[`backend/tests/test_example_dataset.py`](../backend/tests/test_example_dataset.py),
so a change to an analysis threshold fails a test rather than quietly making the
walkthrough wrong.
