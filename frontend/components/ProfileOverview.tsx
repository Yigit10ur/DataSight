import type { ColumnType, DatasetProfile } from "@/lib/api";

import { TypeBadge } from "./TypeBadge";

const TYPE_ORDER: ColumnType[] = ["numeric", "categorical", "datetime", "boolean", "text", "empty"];

const percent = (ratio: number) => `${(ratio * 100).toFixed(1)}%`;
const count = (value: number) => value.toLocaleString("en-US");

function StatTile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <div className="text-xs uppercase tracking-wide text-[var(--text-muted)]">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {note && <div className="mt-0.5 text-xs text-[var(--text-secondary)]">{note}</div>}
    </div>
  );
}

export function ProfileOverview({ profile }: { profile: DatasetProfile }) {
  const idColumns = profile.column_schemas.filter((column) => column.is_probable_id).length;

  return (
    <section className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Rows" value={count(profile.rows)} />
        <StatTile
          label="Columns"
          value={count(profile.columns)}
          note={idColumns > 0 ? `${idColumns} possible ID column${idColumns > 1 ? "s" : ""}` : undefined}
        />
        <StatTile
          label="Missing cells"
          value={percent(profile.missing_ratio)}
          note={`${count(profile.missing_cells)} cells`}
        />
        <StatTile label="Duplicate rows" value={count(profile.duplicate_rows)} />
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm">
        {TYPE_ORDER.filter((type) => profile.type_counts[type]).map((type) => (
          <span key={type} className="flex items-center gap-2">
            <TypeBadge type={type} />
            <span className="tabular-nums text-[var(--text-secondary)]">{profile.type_counts[type]}</span>
          </span>
        ))}
      </div>
    </section>
  );
}
