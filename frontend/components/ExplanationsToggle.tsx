"use client";

import { storeExplanationsChoice, useExplanationsEnabled } from "@/lib/explanations";

const DESCRIPTIONS = {
  on: "AI explanations are on. Turn them off to read a dataset without calling the model.",
  off: "AI explanations are off. Nothing is sent to the model, so reading a dataset costs nothing.",
  pending: "AI explanations",
};

/**
 * Neither state is styled as a fault. Off is a reasonable way to use this tool —
 * every number on the page is computed without a model — so it reads as muted,
 * not as a warning.
 */
export function ExplanationsToggle() {
  const enabled = useExplanationsEnabled();

  function toggle() {
    storeExplanationsChoice(enabled ? "off" : "on");
  }

  const description =
    enabled === null ? DESCRIPTIONS.pending : enabled ? DESCRIPTIONS.on : DESCRIPTIONS.off;

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={enabled === null}
      role="switch"
      aria-checked={enabled ?? false}
      aria-label={description}
      title={description}
      className={`inline-flex h-9 shrink-0 items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2.5 text-xs font-medium transition-colors ${
        enabled
          ? "text-[var(--foreground)]"
          : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
      }`}
    >
      <SparkIcon struck={enabled === false} />
      {enabled === null ? "AI" : enabled ? "AI on" : "AI off"}
    </button>
  );
}

function SparkIcon({ struck }: { struck: boolean }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-3.5"
    >
      <path d="M12 3.5 13.9 9.1 19.5 11 13.9 12.9 12 18.5 10.1 12.9 4.5 11 10.1 9.1Z" />
      {struck && <path d="M4 20 20 4" />}
    </svg>
  );
}
