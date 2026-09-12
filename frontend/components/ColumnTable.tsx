import type { ColumnSchema } from "@/lib/api";

import { TypeBadge } from "./TypeBadge";

function Flags({ column }: { column: ColumnSchema }) {
  const flags = [
    column.is_probable_id && "possible ID",
    column.is_constant && "constant",
    column.is_high_cardinality && "high cardinality",
  ].filter(Boolean) as string[];

  if (flags.length === 0) return <span className="text-[var(--text-muted)]">—</span>;

  return (
    <span className="flex flex-wrap gap-1">
      {flags.map((flag) => (
        <span
          key={flag}
          className="rounded border border-[var(--border)] px-1.5 py-0.5 text-xs whitespace-nowrap text-[var(--flag-warning)]"
        >
          {flag}
        </span>
      ))}
    </span>
  );
}

export function ColumnTable({ columns }: { columns: ColumnSchema[] }) {
  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)]">
      <h2 className="border-b border-[var(--border)] px-4 py-3 text-sm font-semibold">Columns</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-[var(--text-muted)]">
            <tr>
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Type</th>
              <th className="px-4 py-2 text-right font-medium">Missing</th>
              <th className="px-4 py-2 text-right font-medium">Unique</th>
              <th className="px-4 py-2 font-medium">Flags</th>
              <th className="px-4 py-2 font-medium">Sample values</th>
            </tr>
          </thead>
          <tbody>
            {columns.map((column) => (
              <tr key={column.name} className="border-t border-[var(--border)]">
                <td className="px-4 py-2 font-medium whitespace-nowrap">{column.name}</td>
                <td className="px-4 py-2 text-[var(--text-secondary)]">
                  <TypeBadge type={column.inferred_type} />
                </td>
                <td className="px-4 py-2 text-right tabular-nums text-[var(--text-secondary)]">
                  {column.missing_count === 0 ? "—" : `${(column.missing_ratio * 100).toFixed(1)}%`}
                </td>
                <td className="px-4 py-2 text-right tabular-nums text-[var(--text-secondary)]">
                  {column.unique_count.toLocaleString("en-US")}
                </td>
                <td className="px-4 py-2">
                  <Flags column={column} />
                </td>
                <td className="max-w-xs truncate px-4 py-2 font-mono text-xs text-[var(--text-muted)]">
                  {column.sample_values.join(", ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
