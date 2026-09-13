import type { Lineage } from "@/lib/api";

/** Which dataset the dashboard is showing, and how to get back to the file. */
export function LineageTrail({
  lineage,
  onSelect,
}: {
  lineage: Lineage;
  onSelect: (datasetId: string) => void;
}) {
  if (lineage.chain.length < 2) return null;

  return (
    <nav className="flex flex-wrap items-center gap-1.5 text-sm text-[var(--text-muted)]">
      {lineage.chain.map((entry, index) => {
        const here = index === lineage.chain.length - 1;
        const label =
          index === 0 ? entry.filename : `+${entry.recipe?.steps.length ?? 0} steps`;

        return (
          <span key={entry.dataset_id} className="flex items-center gap-1.5">
            {index > 0 && <span aria-hidden>›</span>}
            {here ? (
              <span className="font-medium text-[var(--foreground)]">
                {label} · {entry.rows.toLocaleString("en-US")} rows
              </span>
            ) : (
              <button
                type="button"
                onClick={() => onSelect(entry.dataset_id)}
                className="cursor-pointer underline decoration-dotted underline-offset-4 hover:text-[var(--foreground)]"
              >
                {label}
              </button>
            )}
          </span>
        );
      })}
    </nav>
  );
}
