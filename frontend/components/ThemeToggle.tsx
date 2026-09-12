"use client";

import { useSyncExternalStore } from "react";

import {
  applyTheme,
  readThemeChoice,
  storeThemeChoice,
  systemTheme,
  type ResolvedTheme,
} from "@/lib/theme";

/**
 * data-theme on <html> is the single source of truth: THEME_INIT_SCRIPT sets it
 * before hydration, so the button reads the DOM rather than keeping its own copy.
 */
function subscribe(onStoreChange: () => void) {
  const query = window.matchMedia("(prefers-color-scheme: dark)");

  function followSystem() {
    // An explicitly pinned theme outranks the OS preference.
    if (readThemeChoice() !== "system") return;
    applyTheme(systemTheme());
  }

  const observer = new MutationObserver(onStoreChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });
  query.addEventListener("change", followSystem);

  return () => {
    observer.disconnect();
    query.removeEventListener("change", followSystem);
  };
}

function getSnapshot(): ResolvedTheme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

// The server cannot know the stored choice; the button stays inert until hydration.
function getServerSnapshot(): null {
  return null;
}

export function ThemeToggle() {
  const resolved = useSyncExternalStore<ResolvedTheme | null>(
    subscribe,
    getSnapshot,
    getServerSnapshot,
  );

  function toggle() {
    const next: ResolvedTheme = resolved === "dark" ? "light" : "dark";
    storeThemeChoice(next);
    applyTheme(next);
  }

  const label = resolved === "dark" ? "Switch to light theme" : "Switch to dark theme";

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={resolved === null}
      aria-label={label}
      title={label}
      className="grid size-9 shrink-0 place-items-center rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--text-secondary)] transition-colors hover:text-[var(--foreground)]"
    >
      {resolved === null ? null : resolved === "dark" ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}

function SunIcon() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      className="size-4"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-4"
    >
      <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z" />
    </svg>
  );
}
