"use client";

import { useState } from "react";

import { ColumnTable } from "@/components/ColumnTable";
import { PreviewTable } from "@/components/PreviewTable";
import { ProfileOverview } from "@/components/ProfileOverview";
import { UploadDropzone } from "@/components/UploadDropzone";
import { fetchPreview, uploadDataset, type DatasetPreview, type DatasetProfile } from "@/lib/api";

export default function Home() {
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setIsUploading(true);
    setError(null);
    try {
      const uploaded = await uploadDataset(file);
      setProfile(uploaded);
      setPreview(await fetchPreview(uploaded.dataset_id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Upload failed.");
      setProfile(null);
      setPreview(null);
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-6 py-12">
      <header>
        <h1 className="text-2xl font-semibold">AI Data Insight Engine</h1>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          Upload a dataset and get a data analyst&apos;s first pass over it.
        </p>
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
          <ColumnTable columns={profile.column_schemas} />
          {preview && <PreviewTable preview={preview} />}
        </div>
      )}
    </main>
  );
}
