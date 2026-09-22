"use client";

import { useEffect, useState } from "react";

import { ChartGrid } from "@/components/ChartGrid";
import { AskData } from "@/components/AskData";
import { ColumnTable } from "@/components/ColumnTable";
import { ExplanationsToggle } from "@/components/ExplanationsToggle";
import { InsightList } from "@/components/InsightList";
import { LineageTrail } from "@/components/LineageTrail";
import { ProfileOverview } from "@/components/ProfileOverview";
import { QualityIssues } from "@/components/QualityIssues";
import { QualityScore } from "@/components/QualityScore";
import { RecipeWorkbench } from "@/components/RecipeWorkbench";
import { ThemeToggle } from "@/components/ThemeToggle";
import { UploadDropzone } from "@/components/UploadDropzone";
import { useExplanationsEnabled } from "@/lib/explanations";
import {
  fetchCharts,
  fetchExplanations,
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

/** What the model made of one dataset's findings, tagged with which dataset. */
type Reading = {
  datasetId: string;
  summary: string | null;
  texts: Map<string, string>;
};

const NOTHING = new Map<string, string>();

export default function Home() {
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [charts, setCharts] = useState<ChartSpec[]>([]);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [reading, setReading] = useState<Reading | null>(null);
  const [issues, setIssues] = useState<QualityIssue[]>([]);
  const [score, setScore] = useState<Score | null>(null);
  const [lineage, setLineage] = useState<Lineage | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const explanationsEnabled = useExplanationsEnabled();
  const datasetId = profile?.dataset_id ?? null;

  // A reading belongs to the dataset it was written about. Carrying that with it
  // is what lets the switch turn the text off and on without refetching, and what
  // keeps the previous file's explanations off the screen while the next one loads.
  const wanted = datasetId !== null && explanationsEnabled === true;
  const current = reading?.datasetId === datasetId ? reading : null;

  // The only request that reaches a model, kept out of the upload path so the
  // switch governs it: turned off, it is never sent and nothing is billed; turned
  // back on, it runs for the dataset already on screen instead of asking for the
  // file again. Repeat asks about the same findings are answered from the server's
  // cache, so flipping the switch twice costs what flipping it once did.
  useEffect(() => {
    if (datasetId === null || !explanationsEnabled) return;

    let active = true;
    fetchExplanations(datasetId)
      .then((explained) => {
        if (!active) return;
        setReading({
          datasetId,
          summary: explained.summary,
          texts: new Map(explained.explanations.map((item) => [item.insight_id, item.text])),
        });
      })
      .catch(() => {
        // The findings stand on their own without an explanation. Recorded as an
        // empty reading rather than left pending, so the heading stops saying it
        // is still reading.
        if (active) setReading({ datasetId, summary: null, texts: NOTHING });
      });

    return () => {
      active = false;
    };
  }, [datasetId, explanationsEnabled]);

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
    // Set last: it is what starts the explanation request, and there is no point
    // asking for a reading of findings that are not on the screen yet.
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
          <h1 className="text-2xl font-semibold">AI Data Insight Engine</h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Upload a dataset and get a data analyst&apos;s first pass over it.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <ExplanationsToggle />
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
          <AskData
            key={`questions-${profile.dataset_id}`}
            datasetId={profile.dataset_id}
            enabled={explanationsEnabled}
          />
          {score && <QualityScore score={score} />}
          <InsightList
            insights={insights}
            charts={charts}
            explanations={wanted ? (current?.texts ?? NOTHING) : NOTHING}
            summary={wanted ? (current?.summary ?? null) : null}
            isExplaining={wanted && current === null}
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
