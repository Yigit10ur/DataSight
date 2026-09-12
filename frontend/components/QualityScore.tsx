import type { QualityDimension, QualityScore as Score } from "@/lib/api";

const GOOD_SCORE = 90;
const FAIR_SCORE = 70;

function scoreColor(score: number) {
  if (score >= GOOD_SCORE) return "var(--score-good)";
  return score >= FAIR_SCORE ? "var(--score-fair)" : "var(--score-poor)";
}

function DimensionRow({ dimension }: { dimension: QualityDimension }) {
  if (!dimension.applicable) {
    return (
      <div className="flex items-center gap-3 text-sm text-[var(--text-muted)]">
        <span className="w-32 shrink-0">{dimension.label}</span>
        <span className="flex-1 text-xs">nothing in this dataset to measure</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="w-32 shrink-0 text-[var(--text-secondary)]">{dimension.label}</span>
      <span
        className="h-1.5 flex-1 overflow-hidden rounded-full"
        style={{ backgroundColor: "var(--score-track)" }}
      >
        <span
          className="block h-full rounded-full"
          style={{ width: `${dimension.score}%`, backgroundColor: scoreColor(dimension.score) }}
        />
      </span>
      <span className="w-8 shrink-0 text-right tabular-nums">{dimension.score}</span>
    </div>
  );
}

export function QualityScore({ score }: { score: Score }) {
  return (
    <section className="flex flex-col gap-5 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-4 sm:flex-row sm:items-center sm:gap-8">
      <div className="shrink-0">
        <div className="text-xs uppercase tracking-wide text-[var(--text-muted)]">
          Data quality score
        </div>
        <div className="mt-1 flex items-baseline gap-1">
          <span
            className="text-4xl font-semibold tabular-nums"
            style={{ color: scoreColor(score.score) }}
          >
            {score.score}
          </span>
          <span className="text-sm text-[var(--text-muted)]">/ 100</span>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-2">
        {score.dimensions.map((dimension) => (
          <DimensionRow key={dimension.name} dimension={dimension} />
        ))}
      </div>
    </section>
  );
}
