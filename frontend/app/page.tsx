"use client";

import { useState } from "react";

import { ChartGrid } from "@/components/ChartGrid";
import { ColumnTable } from "@/components/ColumnTable";
import { PreviewTable } from "@/components/PreviewTable";
import { ProfileOverview } from "@/components/ProfileOverview";
import { QualityIssues } from "@/components/QualityIssues";
import { ThemeToggle } from "@/components/ThemeToggle";
import { UploadDropzone } from "@/components/UploadDropzone";
import {
  fetchCharts,
  fetchPreview,
  fetchQuality,
  uploadDataset,
  type ChartSpec,
  type DatasetPreview,
  type DatasetProfile,
  type QualityIssue,
} from "@/lib/api";

export default function Home() {
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [charts, setCharts] = useState<ChartSpec[]>([]);
  const [issues, setIssues] = useState<QualityIssue[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setIsUploading(true);
    setError(null);
    try {
      const uploaded = await uploadDataset(file);
      setProfile(uploaded);
      const [previewed, charted, quality] = await Promise.all([
        fetchPreview(uploaded.dataset_id),
        fetchCharts(uploaded.dataset_id),
        fetchQuality(uploaded.dataset_id),
      ]);
      setPreview(previewed);
      setCharts(charted.charts);
      setIssues(quality.issues);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Upload failed.");
      setProfile(null);
      setPreview(null);
      setCharts([]);
      setIssues([]);
    } finally {
      setIsUploading(false);
    }
  }

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
          <QualityIssues issues={issues} />
          <ChartGrid charts={charts} />
          <ColumnTable columns={profile.column_schemas} />
          {preview && <PreviewTable preview={preview} />}
        </div>
      )}
    </main>
  );
}
