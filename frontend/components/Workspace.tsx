"use client";

import { useEffect, useState } from "react";

import { ChartGrid } from "@/components/ChartGrid";
import { ColumnTable } from "@/components/ColumnTable";
import { InsightList } from "@/components/InsightList";
import { LineageTrail } from "@/components/LineageTrail";
import { ProfileOverview } from "@/components/ProfileOverview";
import { QualityIssues } from "@/components/QualityIssues";
import { QualityScore } from "@/components/QualityScore";
import { RecipeWorkbench } from "@/components/RecipeWorkbench";
import { UploadDropzone } from "@/components/UploadDropzone";
import {
  NotFoundError,
  SignedOutError,
  fetchCharts,
  fetchInsights,
  fetchLineage,
  fetchProfile,
  fetchQuality,
  uploadDataset,
  type ChartSpec,
  type DatasetProfile,
  type Insight,
  type Lineage,
  type QualityIssue,
  type QualityScore as Score,
} from "@/lib/api";

const DATASET_PARAM = "dataset";

/**
 * Keeps the open dataset's ID in the address, or takes it out with null, so that
 * reloading the page reopens what was on screen. Replaced rather than pushed: the
 * lineage trail, not the back button, is how a reader steps between datasets.
 */
export function rememberDataset(id: string | null) {
  const address = new URL(window.location.href);
  if (id) address.searchParams.set(DATASET_PARAM, id);
  else address.searchParams.delete(DATASET_PARAM);
  window.history.replaceState(null, "", address);
}

function datasetInAddress(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get(DATASET_PARAM);
}

type Props = {
  /** The session ended while working; the page goes back to logging in. */
  onSignedOut: () => void;
};

/** Everything a signed-in reader sees: the upload area and the dashboard under it. */
export function Workspace({ onSignedOut }: Props) {
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [charts, setCharts] = useState<ChartSpec[]>([]);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [issues, setIssues] = useState<QualityIssue[]>([]);
  const [score, setScore] = useState<Score | null>(null);
  const [lineage, setLineage] = useState<Lineage | null>(null);
  const [isBusy, setIsBusy] = useState(() => datasetInAddress() !== null);
  const [error, setError] = useState<string | null>(null);

  /** Put one dataset on the screen, whether it was uploaded, shaped or stepped back to. */
  async function show(shown: DatasetProfile) {
    const id = shown.dataset_id;
    const [charted, quality, found, trail] = await Promise.all([
      fetchCharts(id),
      fetchQuality(id),
      fetchInsights(id),
      fetchLineage(id),
    ]);
    setCharts(charted.charts);
    setIssues(quality.issues);
    setScore(quality.score);
    setInsights(found.insights);
    setLineage(trail);
    setProfile(shown);
    rememberDataset(id);
  }

  async function load(fetching: () => Promise<DatasetProfile>) {
    setIsBusy(true);
    setError(null);
    try {
      await show(await fetching());
    } catch (cause) {
      fail(cause);
    } finally {
      setIsBusy(false);
    }
  }

  /** Say what went wrong and clear the dashboard, rather than leave half of one. */
  function fail(cause: unknown) {
    if (cause instanceof SignedOutError) {
      onSignedOut();
      return;
    }
    setError(
      cause instanceof NotFoundError
        ? "That dataset has expired or is no longer available. Datasets are temporary; " +
            "upload the file again to carry on."
        : cause instanceof Error
          ? cause.message
          : "That did not work.",
    );
    rememberDataset(null);
    setProfile(null);
    setCharts([]);
    setIssues([]);
    setScore(null);
    setInsights([]);
    setLineage(null);
  }

  // Reopen the dataset a reload, or logging back in, left in the address. Busy
  // from the first render, so the upload area never looks idle while it loads.
  useEffect(() => {
    const id = datasetInAddress();
    if (id) {
      fetchProfile(id)
        .then(show)
        .catch(fail)
        .finally(() => setIsBusy(false));
    }
    // Only on arrival: afterwards the address follows what is shown, not the reverse.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // A chart that already sits inside a finding does not need to be shown again.
  const charted = new Set(insights.map((insight) => insight.chart_id));
  const remainingCharts = charts.filter((chart) => !charted.has(chart.id));

  return (
    <>
      <UploadDropzone onFile={(file) => load(() => uploadDataset(file))} isUploading={isBusy} />

      {error && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm text-[var(--flag-warning)]">
          {error}
        </div>
      )}

      {profile && (
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-1 text-sm text-[var(--text-secondary)]">
            <span className="font-medium text-[var(--foreground)]">{profile.filename}</span>
            {lineage && (
              <LineageTrail
                lineage={lineage}
                onSelect={(id) => load(() => fetchProfile(id))}
              />
            )}
          </div>
          <ProfileOverview profile={profile} />
          {score && <QualityScore score={score} />}
          <InsightList
            insights={insights}
            charts={charts}
          />
          <QualityIssues issues={issues} />
          <ChartGrid
            charts={remainingCharts}
            title={remainingCharts.length === charts.length ? "Charts" : "Other charts"}
          />
          <ColumnTable columns={profile.column_schemas} />
          <RecipeWorkbench
            key={profile.dataset_id}
            profile={profile}
            onDerived={(derived) => load(async () => derived)}
          />
        </div>
      )}
    </>
  );
}
