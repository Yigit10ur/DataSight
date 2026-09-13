"use client";

import { useSyncExternalStore } from "react";

export type ExplanationsChoice = "on" | "off";

export const EXPLANATIONS_STORAGE_KEY = "datasight-explanations";

/**
 * Whether the dashboard may ask the API for model-written explanations.
 *
 * Off is the setting that costs nothing: the request is never sent, so no tokens
 * are billed. Everything else on the page — the profile, the quality score, the
 * findings, the charts — is computed in Python and unaffected by this choice.
 *
 * Unlike the theme, this cannot be read before hydration: nothing paints
 * differently for it, and the first request only goes out after an upload.
 */
let choice: ExplanationsChoice | null = null;

const listeners = new Set<() => void>();

export function readExplanationsChoice(): ExplanationsChoice {
  if (choice === null) {
    try {
      choice = localStorage.getItem(EXPLANATIONS_STORAGE_KEY) === "off" ? "off" : "on";
    } catch {
      choice = "on";
    }
  }
  return choice;
}

export function storeExplanationsChoice(next: ExplanationsChoice): void {
  // Held in the module as well as storage, so a blocked localStorage still leaves
  // a working switch — it is only the remembering that is lost.
  choice = next;
  try {
    localStorage.setItem(EXPLANATIONS_STORAGE_KEY, next);
  } catch {
    // Private mode or blocked storage: the choice holds for this page view.
  }
  for (const listener of listeners) listener();
}

function subscribe(onStoreChange: () => void) {
  listeners.add(onStoreChange);
  return () => {
    listeners.delete(onStoreChange);
  };
}

function getSnapshot(): boolean {
  return readExplanationsChoice() === "on";
}

// The server cannot know the stored choice. Null means "not decided yet", which
// callers read as off: never spend money on a preference that has not loaded.
function getServerSnapshot(): null {
  return null;
}

export function useExplanationsEnabled(): boolean | null {
  return useSyncExternalStore<boolean | null>(subscribe, getSnapshot, getServerSnapshot);
}
