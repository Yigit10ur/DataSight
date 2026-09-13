"use client";

import { useEffect, useMemo, useState } from "react";

import {
  applyRecipe,
  exportRecipe,
  previewRecipe,
  type AnalyzeStep,
  type ColumnSchema,
  type DatasetProfile,
  type PlannedColumn,
  type RecipePreview,
  type RecipeStep,
} from "@/lib/api";

import { AnalysisResult } from "./AnalysisResult";
import { RecipeSteps } from "./RecipeSteps";
import { RecipeTable } from "./RecipeTable";

function planned(schema: ColumnSchema): PlannedColumn {
  return {
    name: schema.name,
    inferred_type: schema.inferred_type,
    is_probable_id: schema.is_probable_id,
    is_high_cardinality: schema.is_high_cardinality,
  };
}

/**
 * Shaping a dataset by hand: the recipe on one side, what it produces on the other.
 *
 * Every edit asks the server what the recipe would do and stores nothing, so a
 * reader can try a dozen shapes without making a dozen datasets. Saving is the only
 * thing that keeps one, and what it keeps is a dataset like any other.
 *
 * A recipe belongs to the dataset it was written against, so the caller keys this on
 * the dataset id: moving to another one — including the one that was just saved —
 * remounts it, and it starts from nothing.
 */
export function RecipeWorkbench({
  profile,
  onDerived,
}: {
  profile: DatasetProfile;
  onDerived: (derived: DatasetProfile) => void;
}) {
  const [steps, setSteps] = useState<RecipeStep[]>([]);
  const [analyze, setAnalyze] = useState<AnalyzeStep | null>(null);
  const [result, setResult] = useState<RecipePreview | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const datasetId = profile.dataset_id;
  const sourceColumns = useMemo(() => profile.column_schemas.map(planned), [profile]);

  useEffect(() => {
    let active = true;

    previewRecipe(datasetId, { steps, analyze })
      .then((preview) => {
        if (active) setResult(preview);
      })
      .catch(() => {
        // The panel keeps what it had rather than emptying the table under a reader
        // who is mid-edit; the next keystroke asks again.
        if (active) setError(null);
      });

    return () => {
      active = false;
    };
  }, [datasetId, steps, analyze]);

  function add(step: RecipeStep | AnalyzeStep, terminal: boolean) {
    setError(null);
    if (terminal) setAnalyze(step as AnalyzeStep);
    else setSteps((current) => [...current, step as RecipeStep]);
  }

  async function download() {
    setIsDownloading(true);
    setError(null);
    try {
      const { blob, filename } = await exportRecipe(datasetId, { steps, analyze: null });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The rows could not be downloaded.");
    } finally {
      setIsDownloading(false);
    }
  }

  async function save() {
    setIsSaving(true);
    setError(null);
    try {
      onDerived(await applyRecipe(datasetId, { steps, analyze: null }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The recipe could not be saved.");
    } finally {
      setIsSaving(false);
    }
  }

  const columns = result?.columns ?? sourceColumns;

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold">Shape this data</h2>

      <div className="flex flex-col gap-3 lg:flex-row lg:items-start">
        <RecipeSteps
          steps={steps}
          analyze={analyze}
          reports={result?.reports ?? []}
          refusal={result?.refusal ?? null}
          columns={columns}
          sourceColumns={sourceColumns}
          onAdd={add}
          onRemove={(index) =>
            setSteps((current) => current.filter((_, at) => at !== index))
          }
          onRemoveAnalysis={() => setAnalyze(null)}
          onSave={save}
          onDownload={download}
          isSaving={isSaving}
          isDownloading={isDownloading}
          error={error}
        />

        {result && (
          <RecipeTable
            preview={result.preview}
            columns={columns}
            sourceRows={result.source_rows}
            sourceColumns={sourceColumns.length}
            onAdd={add}
          />
        )}
      </div>

      {result?.analysis && <AnalysisResult analysis={result.analysis} />}
    </section>
  );
}
