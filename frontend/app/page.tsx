"use client";

import { useState } from "react";

import { ChartGrid } from "@/components/ChartGrid";
import { ColumnTable } from "@/components/ColumnTable";
import { InsightList } from "@/components/InsightList";
import { PreviewTable } from "@/components/PreviewTable";
import { ProfileOverview } from "@/components/ProfileOverview";
import { QualityIssues } from "@/components/QualityIssues";
import { QualityScore } from "@/components/QualityScore";
import { ThemeToggle } from "@/components/ThemeToggle";
import { UploadDropzone } from "@/components/UploadDropzone";
import {
  fetchCharts,
  fetchExplanations,
  fetchInsights,
  fetchPreview,
  fetchQuality,
  uploadDataset,
  type ChartSpec,
  type DatasetPreview,
  type DatasetProfile,
  type Insight,
  type QualityIssue,
  type QualityScore as Score,
} from "@/lib/api";

export default function Home() {
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [charts, setCharts] = useState<ChartSpec[]>([]);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [explanations, setExplanations] = useState(new Map<string, string>());
  const [summary, setSummary] = useState<string | null>(null);
  const [isExplaining, setIsExplaining] = useState(false);
  const [issues, setIssues] = useState<QualityIssue[]>([]);
  const [score, setScore] = useState<Score | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setIsUploading(true);
    setError(null);
    setExplanations(new Map());
    setSummary(null);
    try {
      const uploaded = await uploadDataset(file);
      setProfile(uploaded);
      const [previewed, charted, quality, found] = await Promise.all([
        fetchPreview(uploaded.dataset_id),
        fetchCharts(uploaded.dataset_id),
        fetchQuality(uploaded.dataset_id),
        fetchInsights(uploaded.dataset_id),
      ]);
      setPreview(previewed);
      setCharts(charted.charts);
      setIssues(quality.issues);
      setScore(quality.score);
      setInsights(found.insights);

      // Asked for separately and awaited last: a slow model, or none at all, must
      // not keep the computed numbers off the screen.
      setIsExplaining(true);
      try {
        const explained = await fetchExplanations(uploaded.dataset_id);
        setSummary(explained.summary);
        setExplanations(
          new Map(explained.explanations.map((item) => [item.insight_id, item.text])),
        );
      } catch {
        // The findings stand on their own without an explanation.
      } finally {
        setIsExplaining(false);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Upload failed.");
      setProfile(null);
      setPreview(null);
      setCharts([]);
      setIssues([]);
      setScore(null);
      setInsights([]);
      setExplanations(new Map());
      setSummary(null);
    } finally {
      setIsUploading(false);
    }
  }

  // A chart that already sits inside a finding does not need to be shown again.
  const explained = new Set(insights.map((insight) => insight.chart_id));
  const remainingCharts = charts.filter((chart) => !explained.has(chart.id));

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-6 py-12">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">AI Data Insight Engine</h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Upload a dataset and get a data analyst&apos;s first pass over it.
          </p>
        </div>
        <ThemeToggle />
      </header>

      <UploadDropzone onFile={handleFile} isUploading={isUploading} />

      {error && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm text-[var(--flag-warning)]">
          {error}
        </div>
      )}

      {profile && (
        <div className="flex flex-col gap-6">
          <div className="text-sm text-[var(--text-secondary)]">
            <span className="font-medium text-[var(--foreground)]">{profile.filename}</span>
          </div>
          <ProfileOverview profile={profile} />
          {score && <QualityScore score={score} />}
          <InsightList
            insights={insights}
            charts={charts}
            explanations={explanations}
            summary={summary}
            isExplaining={isExplaining}
          />
          <QualityIssues issues={issues} />
          <ChartGrid
            charts={remainingCharts}
            title={remainingCharts.length === charts.length ? "Charts" : "Other charts"}
          />
          <ColumnTable columns={profile.column_schemas} />
          {preview && <PreviewTable preview={preview} />}
        </div>
      )}
    </main>
  );
}
