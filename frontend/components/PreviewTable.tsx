import type { DatasetPreview } from "@/lib/api";

export function PreviewTable({ preview }: { preview: DatasetPreview }) {
  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)]">
      <h2 className="flex items-baseline justify-between border-b border-[var(--border)] px-4 py-3 text-sm font-semibold">
        Data preview
        <span className="font-normal text-[var(--text-muted)]">
          first {preview.rows.length.toLocaleString("en-US")} of{" "}
          {preview.total_rows.toLocaleString("en-US")} rows
        </span>
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-[var(--text-muted)]">
            <tr>
              {preview.columns.map((column) => (
                <th key={column} className="px-4 py-2 font-medium whitespace-nowrap">
                  {column}
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
                    <td key={column} className="px-4 py-2 whitespace-nowrap">
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
          </tbody>
        </table>
      </div>
    </section>
  );
}
