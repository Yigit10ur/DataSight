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
import { ThemeToggle } from "@/components/ThemeToggle";
import { UploadDropzone } from "@/components/UploadDropzone";
import {
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

export default function Home() {
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
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-6 py-12">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">DataSight</h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Upload a dataset and get a data analyst&apos;s first pass over it.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <ThemeToggle />
        </div>
      </header>

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
    </main>
  );
}
