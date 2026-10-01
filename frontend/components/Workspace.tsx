"use client";

import { useState } from "react";

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
  const [isBusy, setIsBusy] = useState(false);
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
  }

  async function load(fetching: () => Promise<DatasetProfile>) {
    setIsBusy(true);
    setError(null);
    try {
      await show(await fetching());
    } catch (cause) {
      if (cause instanceof SignedOutError) {
        onSignedOut();
        return;
      }
      setError(cause instanceof Error ? cause.message : "That did not work.");
      setProfile(null);
      setCharts([]);
      setIssues([]);
      setScore(null);
      setInsights([]);
      setLineage(null);
    } finally {
      setIsBusy(false);
    }
  }

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
