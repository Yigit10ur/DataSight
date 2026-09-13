"use client";

import type { AnalyzeStep, PlannedColumn, RecipeStep, StepRefusal, StepReport } from "@/lib/api";
import { summarise, summariseAnalysis, TABLE_OPTIONS } from "@/lib/recipe";

import { StepMenu } from "./StepMenu";

/**
 * The recipe itself, which is also the undo: removing a line removes the step.
 *
 * Nothing here is hidden from the reader — every change they have made is a line
 * they can read, and the order they are in is the order they run in.
 */
export function RecipeSteps({
  steps,
  analyze,
  reports,
  refusal,
  columns,
  sourceColumns,
  onAdd,
  onRemove,
  onRemoveAnalysis,
  onSave,
  isSaving,
  saveError,
}: {
  steps: RecipeStep[];
  analyze: AnalyzeStep | null;
  reports: StepReport[];
  refusal: StepRefusal | null;
  columns: PlannedColumn[];
  sourceColumns: PlannedColumn[];
  onAdd: (step: RecipeStep | AnalyzeStep, terminal: boolean) => void;
  onRemove: (index: number) => void;
  onRemoveAnalysis: () => void;
  onSave: () => void;
  isSaving: boolean;
  saveError: string | null;
}) {
  const canSave = steps.length > 0 && refusal === null && analyze === null;

  return (
    <section className="flex w-full shrink-0 flex-col gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3 lg:w-72">
      <h3 className="text-sm font-semibold">Recipe</h3>

      {steps.length === 0 && analyze === null && (
        <p className="text-sm text-[var(--text-muted)]">
          Click a column heading in the table to shape it, or add a step below.
        </p>
      )}

      <ol className="flex flex-col gap-1">
        {steps.map((step, index) => (
          <li key={index} className="flex flex-col">
            <div className="flex items-start gap-2 text-sm">
              <span className="w-4 shrink-0 pt-0.5 text-right tabular-nums text-[var(--text-muted)]">
                {index + 1}
              </span>
              <span className="flex-1 break-words">{summarise(step)}</span>
              <button
                type="button"
                aria-label={`Remove step ${index + 1}`}
                onClick={() => onRemove(index)}
                className="shrink-0 cursor-pointer px-1 text-[var(--text-muted)] hover:text-[var(--foreground)]"
              >
                ×
              </button>
            </div>
            <StepNote
              note={reports[index]?.note ?? null}
              reason={refusal?.step_index === index ? refusal.reason : null}
            />
          </li>
        ))}

        {analyze && (
          <li className="mt-1 flex flex-col border-t border-[var(--border)] pt-2">
            <div className="flex items-start gap-2 text-sm">
              <span className="w-4 shrink-0 pt-0.5 text-right text-[var(--text-muted)]">?</span>
              <span className="flex-1 break-words">{summariseAnalysis(analyze)}</span>
              <button
                type="button"
                aria-label="Remove the question"
                onClick={onRemoveAnalysis}
                className="shrink-0 cursor-pointer px-1 text-[var(--text-muted)] hover:text-[var(--foreground)]"
              >
                ×
              </button>
            </div>
            <StepNote
              note={null}
              reason={refusal?.step_index === steps.length ? refusal.reason : null}
            />
          </li>
        )}
      </ol>

      <StepMenu
        options={TABLE_OPTIONS}
        columns={columns.length > 0 ? columns : sourceColumns}
        column=""
        onAdd={({ step, terminal }) => onAdd(step, terminal)}
        label={<span className="text-sm text-[var(--text-secondary)]">+ add a step</span>}
      />

      <div className="mt-auto flex flex-col gap-2 border-t border-[var(--border)] pt-3">
        <button
          type="button"
          disabled={!canSave || isSaving}
          onClick={onSave}
          className="cursor-pointer rounded-md bg-[var(--foreground)] px-3 py-1.5 text-sm font-medium text-[var(--background)] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {isSaving ? "Saving…" : "Save as a dataset"}
        </button>
        {analyze !== null && (
          <p className="text-xs text-[var(--text-muted)]">
            A question answers with a finding rather than a table. Remove it to save the rows it
            was computed from.
          </p>
        )}
        {saveError && <p className="text-xs text-[var(--flag-warning)]">{saveError}</p>}
      </div>
    </section>
  );
}

function StepNote({ note, reason }: { note: string | null; reason: string | null }) {
  if (!reason && !note) return null;

  return (
    <p
      className={`ml-6 text-xs ${
        reason ? "text-[var(--flag-warning)]" : "text-[var(--text-muted)]"
      }`}
    >
      {reason ?? note}
    </p>
  );
}
