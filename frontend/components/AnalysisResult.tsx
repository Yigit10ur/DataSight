import type { RecipeAnalysis } from "@/lib/api";

import { Chart } from "./Chart";

function format(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const rounded = Math.abs(value) >= 100 ? Math.round(value) : Number(value.toFixed(2));
  return rounded.toLocaleString("en-US");
}

function percent(ratio: number | null): string {
  return `${(ratio ?? 0) >= 0 ? "up" : "down"} ${format(Math.abs((ratio ?? 0) * 100))}%`;
}

/** One sentence about what was found, and anything that should temper it. */
function read(analysis: RecipeAnalysis): { headline: string; caveats: string[] } {
  const { comparison, correlation, timeline, numeric, categorical } = analysis;

  if (comparison) {
    const ratio = comparison.mean_ratio;
    const caveats = [`Computed from ${format(comparison.sample_size)} rows.`];
    if (comparison.p_value !== null && comparison.p_value > 0.05) {
      caveats.push(
        `A difference this size could come up by chance (p = ${format(comparison.p_value)}).`,
      );
    }
    if (comparison.ignored_group_count > 0) {
      caveats.push(
        `${comparison.ignored_group_count} groups had too few rows to describe and were left out.`,
      );
    }
    return {
      headline:
        `${comparison.value_column} is highest for ${comparison.highest_group} and lowest ` +
        `for ${comparison.lowest_group}` +
        (ratio ? `, ${format(ratio)}× apart on average.` : "."),
      caveats,
    };
  }

  if (correlation) {
    return {
      headline:
        `${correlation.column_a} and ${correlation.column_b} move together ` +
        `(r = ${format(correlation.pearson)}).`,
      caveats: [
        `Computed from ${format(correlation.sample_size)} rows.`,
        "Two things moving together is not one causing the other.",
      ],
    };
  }

  if (timeline) {
    const direction =
      timeline.trend === "flat" ? "has stayed about level" : `is ${timeline.trend}`;
    return {
      headline:
        `${timeline.value_column} ${direction} from ${timeline.start} to ${timeline.end}` +
        (timeline.change_ratio !== null ? `, ${percent(timeline.change_ratio)}.` : "."),
      caveats: [`${timeline.aggregation} over ${format(timeline.sample_size)} rows.`],
    };
  }

  if (numeric) {
    return {
      headline:
        `${numeric.column} runs from ${format(numeric.minimum)} to ${format(numeric.maximum)}, ` +
        `with a typical value of ${format(numeric.median)}.`,
      caveats: [
        `${format(numeric.count)} values, ${format(numeric.missing_count)} missing.`,
        ...(numeric.outlier_count > 0
          ? [`${format(numeric.outlier_count)} values sit far outside the rest.`]
          : []),
      ],
    };
  }

  if (categorical) {
    const top = categorical.top_categories[0];
    return {
      headline: top
        ? `${categorical.column} is most often ${top.value} (${format(top.ratio * 100)}% of rows), ` +
          `across ${format(categorical.unique_count)} distinct values.`
        : `${categorical.column} has no values to describe.`,
      caveats: [`${format(categorical.count)} values, ${format(categorical.missing_count)} missing.`],
    };
  }

  return { headline: "Nothing was found.", caveats: [] };
}

export function AnalysisResult({ analysis }: { analysis: RecipeAnalysis }) {
  const { headline, caveats } = read(analysis);
  // What the recipe did to the meaning of the rows comes first: it frames every
  // number underneath it.
  const all = [...analysis.caveats, ...caveats];

  return (
    <section className="flex flex-col gap-3">
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <p className="text-sm">{headline}</p>
        {all.length > 0 && (
          <ul className="mt-2 flex flex-col gap-0.5">
            {all.map((caveat) => (
              <li key={caveat} className="text-xs text-[var(--text-muted)]">
                {caveat}
              </li>
            ))}
          </ul>
        )}
      </div>
      {analysis.chart && <Chart spec={analysis.chart} />}
    </section>
  );
}
