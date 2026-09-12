import type { ChartSpec, Insight, InsightType } from "@/lib/api";

import { Chart } from "./Chart";

const TYPE_LABELS: Record<InsightType, string> = {
  correlation: "relationship",
  group_difference: "group difference",
  trend: "trend",
  seasonality: "seasonality",
  sudden_change: "sudden change",
  outliers: "extreme values",
  skewed_distribution: "distribution",
  dominant_category: "dominant value",
  rare_categories: "rare values",
  missing_data: "missing data",
};

// Findings about the subject of the data read differently from findings about the
// state of the file, so they are coloured apart rather than all alike.
const TYPE_COLORS: Record<InsightType, string> = {
  correlation: "var(--type-numeric)",
  group_difference: "var(--type-numeric)",
  trend: "var(--type-datetime)",
  seasonality: "var(--type-datetime)",
  sudden_change: "var(--type-datetime)",
  outliers: "var(--type-categorical)",
  skewed_distribution: "var(--type-categorical)",
  dominant_category: "var(--type-boolean)",
  rare_categories: "var(--type-boolean)",
  missing_data: "var(--type-empty)",
};

export function InsightCard({
  insight,
  chart,
  explanation,
}: {
  insight: Insight;
  chart?: ChartSpec;
  explanation?: string;
}) {
  return (
    <article className="flex flex-col gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-xs text-[var(--text-muted)]">
        <span
          aria-hidden
          className="size-2 shrink-0 rounded-full"
          style={{ backgroundColor: TYPE_COLORS[insight.insight_type] }}
        />
        {TYPE_LABELS[insight.insight_type]}
      </span>

      <p className="text-sm leading-relaxed">{insight.message}</p>

      {explanation && (
        <p
          className="border-l-2 pl-3 text-sm leading-relaxed text-[var(--text-secondary)]"
          style={{ borderColor: TYPE_COLORS[insight.insight_type] }}
        >
          {explanation}
        </p>
      )}

      {insight.caveats.map((caveat) => (
        <p key={caveat} className="text-xs leading-relaxed text-[var(--text-muted)]">
          {caveat}
        </p>
      ))}

      {chart && <Chart spec={chart} showTitle={false} />}
    </article>
  );
}
