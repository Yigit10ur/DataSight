import type { ChartSpec, Insight } from "@/lib/api";

import { InsightCard } from "./InsightCard";

export function InsightList({
  insights,
  charts,
  explanations,
  isExplaining,
}: {
  insights: Insight[];
  charts: ChartSpec[];
  explanations: Map<string, string>;
  isExplaining: boolean;
}) {
  const byId = new Map(charts.map((chart) => [chart.id, chart]));

  return (
    <section className="flex flex-col gap-3">
      <h2 className="flex items-baseline justify-between text-sm font-semibold">
        What stands out
        {insights.length > 0 && (
          <span className="font-normal text-[var(--text-muted)]">
            {isExplaining
              ? "reading the findings\u2026"
              : `${insights.length} finding${insights.length > 1 ? "s" : ""}, most important first`}
          </span>
        )}
      </h2>

      {insights.length === 0 ? (
        <p className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm text-[var(--text-secondary)]">
          Nothing in this dataset stands out strongly enough to report: no strong
          relationships, no large differences between groups, no clear movement over time.
          The charts and tables below still describe it in full.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {insights.map((insight) => (
            <InsightCard
              key={insight.id}
              insight={insight}
              chart={insight.chart_id ? byId.get(insight.chart_id) : undefined}
              explanation={explanations.get(insight.id)}
            />
          ))}
        </div>
      )}
    </section>
  );
}
