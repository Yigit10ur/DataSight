"use client";

import { useState, type FormEvent } from "react";

import { askDataset, type QuestionResponse } from "@/lib/api";

import { Chart } from "./Chart";

export function AskData({
  datasetId,
  enabled,
}: {
  datasetId: string;
  enabled: boolean | null;
}) {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<QuestionResponse[]>([]);
  const [isAsking, setIsAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const asked = question.trim();
    if (!asked || enabled !== true) return;
    setIsAsking(true);
    setError(null);
    try {
      const response = await askDataset(datasetId, asked, true);
      setTurns((current) => [...current, response]);
      setQuestion("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The question could not be answered.");
    } finally {
      setIsAsking(false);
    }
  }

  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="text-sm font-semibold">Ask your data</h2>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          {enabled
            ? "AI chooses a validated analysis plan. Python performs every calculation."
            : "Turn on AI above to ask a question. No model is called while AI is off."}
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {turns.map((turn, index) => (
          <article
            key={`${index}-${turn.question}`}
            className="flex flex-col gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4"
          >
            <p className="text-sm font-medium">{turn.question}</p>
            {turn.status === "refused" ? (
              <p role="alert" className="text-sm text-[var(--flag-warning)]">
                {turn.refusal}
              </p>
            ) : (
              <>
                <p className="text-sm leading-relaxed">{turn.answer}</p>
                {!turn.explained && turn.explanation_reason && (
                  <p className="text-xs text-[var(--text-muted)]">
                    Showing the verified Python result because the model explanation was unavailable.
                  </p>
                )}
                {turn.rows.length > 0 && <ResultTable rows={turn.rows} />}
                {turn.result_truncated && (
                  <p className="text-xs text-[var(--text-muted)]">
                    The result is capped to protect privacy and prompt size.
                  </p>
                )}
                {turn.chart && <Chart spec={turn.chart} />}
              </>
            )}
          </article>
        ))}
      </div>

      <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row">
        <label className="sr-only" htmlFor="data-question">Question about this dataset</label>
        <input
          id="data-question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          disabled={enabled !== true || isAsking}
          placeholder="Which products generate the most revenue?"
          className="min-w-0 flex-1 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={enabled !== true || isAsking || question.trim().length === 0}
          className="rounded-lg bg-[var(--foreground)] px-4 py-2 text-sm font-medium text-[var(--background)] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {isAsking ? "Analyzing…" : "Ask"}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-[var(--flag-warning)]">{error}</p>}
    </section>
  );
}

function ResultTable({ rows }: { rows: Record<string, unknown>[] }) {
  const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))];
  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
      <table className="w-full text-left text-sm">
        <thead className="text-xs text-[var(--text-muted)]">
          <tr>{columns.map((column) => <th key={column} className="px-3 py-2">{column}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} className="border-t border-[var(--border)]">
              {columns.map((column) => (
                <td key={column} className="px-3 py-2">{String(row[column] ?? "—")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
