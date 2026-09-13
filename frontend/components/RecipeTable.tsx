"use client";

import type { AnalyzeStep, DatasetPreview, PlannedColumn, RecipeStep } from "@/lib/api";
import { optionsFor } from "@/lib/recipe";

import { StepMenu } from "./StepMenu";
import { TypeBadge } from "./TypeBadge";

/**
 * The preview, and the place steps are made.
 *
 * A heading opens only the operations that suit that column as it stands at this
 * point in the recipe, which is why the projected schema is passed in beside the
 * rows rather than read off them.
 */
export function RecipeTable({
  preview,
  columns,
  sourceRows,
  sourceColumns,
  onAdd,
}: {
  preview: DatasetPreview;
  columns: PlannedColumn[];
  sourceRows: number;
  sourceColumns: number;
  onAdd: (step: RecipeStep | AnalyzeStep, terminal: boolean) => void;
}) {
  const rows = preview.total_rows;
  const shown = preview.columns.length;

  return (
    <section className="flex min-w-0 flex-1 flex-col rounded-xl border border-[var(--border)] bg-[var(--surface)]">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-[var(--text-muted)]">
            <tr>
              {columns.map((column) => (
                <th key={column.name} className="px-2 py-2 font-medium whitespace-nowrap">
                  <StepMenu
                    options={optionsFor(column)}
                    columns={columns}
                    column={column.name}
                    onAdd={({ step, terminal }) => onAdd(step, terminal)}
                    label={
                      <span className="flex items-center gap-1.5">
                        <span className="text-sm font-medium text-[var(--foreground)]">
                          {column.name}
                        </span>
                        <TypeBadge type={column.inferred_type} />
                        <span aria-hidden className="text-[var(--text-muted)]">
                          ▾
                        </span>
                      </span>
                    }
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview.rows.map((row, index) => (
              <tr key={index} className="border-t border-[var(--border)]">
                {preview.columns.map((column) => {
                  const value = row[column];
                  return (
                    <td key={column} className="px-3 py-1.5 whitespace-nowrap">
                      {value === null ? (
                        <span className="text-[var(--text-muted)] italic">null</span>
                      ) : (
                        <span className={typeof value === "number" ? "tabular-nums" : ""}>
                          {String(value)}
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
            {preview.rows.length === 0 && (
              <tr className="border-t border-[var(--border)]">
                <td
                  colSpan={Math.max(1, shown)}
                  className="px-3 py-6 text-center text-[var(--text-muted)]"
                >
                  No rows are left.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="border-t border-[var(--border)] px-3 py-2 text-xs text-[var(--text-muted)]">
        <Count from={sourceRows} to={rows} one="row" many="rows" />
        {" · "}
        <Count from={sourceColumns} to={shown} one="column" many="columns" />
      </p>
    </section>
  );
}

function Count({
  from,
  to,
  one,
  many,
}: {
  from: number;
  to: number;
  one: string;
  many: string;
}) {
  const word = to === 1 ? one : many;
  if (from === to) return <>{`${to.toLocaleString("en-US")} ${word}`}</>;
  return (
    <>
      {from.toLocaleString("en-US")} → {to.toLocaleString("en-US")} {word}
    </>
  );
}
