import type { QualityIssue, Severity } from "@/lib/api";

const SEVERITY_COLORS: Record<Severity, string> = {
  serious: "var(--severity-serious)",
  warning: "var(--severity-warning)",
  info: "var(--severity-info)",
};

export function QualityIssues({ issues }: { issues: QualityIssue[] }) {
  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)]">
      <h2 className="flex items-baseline justify-between border-b border-[var(--border)] px-4 py-3 text-sm font-semibold">
        Data quality
        <span className="font-normal text-[var(--text-muted)]">
          {issues.length === 0
            ? "no issues found"
            : `${issues.length} issue${issues.length > 1 ? "s" : ""}`}
        </span>
      </h2>

      {issues.length === 0 ? (
        <p className="px-4 py-3 text-sm text-[var(--text-secondary)]">
          No missing values, duplicates, outliers or inconsistent categories were detected.
        </p>
      ) : (
        <ul>
          {issues.map((issue) => (
            <li
              key={issue.id}
              className="flex gap-3 border-t border-[var(--border)] px-4 py-3 text-sm first:border-t-0"
            >
              <span
                className="mt-1 size-2 shrink-0 rounded-full"
                style={{ backgroundColor: SEVERITY_COLORS[issue.severity] }}
                aria-hidden
              />
              <div className="min-w-0">
                <div>{issue.message}</div>
                <div className="mt-0.5 text-xs text-[var(--text-muted)]">
                  {issue.severity} · {issue.issue_type.replace(/_/g, " ")}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
