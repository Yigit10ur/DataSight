import type { ColumnType } from "@/lib/api";

const TYPE_COLORS: Record<ColumnType, string> = {
  numeric: "var(--type-numeric)",
  categorical: "var(--type-categorical)",
  datetime: "var(--type-datetime)",
  boolean: "var(--type-boolean)",
  text: "var(--type-text)",
  empty: "var(--type-empty)",
};

export function TypeBadge({ type }: { type: ColumnType }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      <span
        aria-hidden
        className="size-2 shrink-0 rounded-full"
        style={{ backgroundColor: TYPE_COLORS[type] }}
      />
      {type}
    </span>
  );
}
