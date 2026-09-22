"use client";

import { useRef, useState, type DragEvent } from "react";

type Props = {
  onFile: (file: File) => void;
  isUploading: boolean;
};

export function UploadDropzone({ onFile, isUploading }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) onFile(file);
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      className={`rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
        isDragging ? "border-[var(--type-numeric)] bg-[var(--surface)]" : "border-[var(--border)]"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        aria-label="Upload dataset"
        accept=".csv,.xlsx"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onFile(file);
          event.target.value = "";
        }}
      />

      <p className="text-base font-medium">Drop a CSV or Excel file here</p>
      <p className="mt-1 text-sm text-[var(--text-secondary)]">
        Supported formats: .csv, .xlsx — up to 100 MB
      </p>

      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={isUploading}
        className="mt-5 rounded-lg bg-[var(--foreground)] px-4 py-2 text-sm font-medium text-[var(--background)] disabled:opacity-50"
      >
        {isUploading ? "Analyzing…" : "Choose file"}
      </button>
    </div>
  );
}
