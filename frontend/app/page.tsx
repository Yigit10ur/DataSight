"use client";

import { useEffect, useState } from "react";

import { API_URL, fetchHealth } from "@/lib/api";

type Status =
  | { state: "loading" }
  | { state: "connected"; app: string }
  | { state: "error"; message: string };

export default function Home() {
  const [status, setStatus] = useState<Status>({ state: "loading" });

  useEffect(() => {
    fetchHealth()
      .then((health) => setStatus({ state: "connected", app: health.app }))
      .catch((error: Error) => setStatus({ state: "error", message: error.message }));
  }, []);

  return (
    <main className="mx-auto flex max-w-2xl flex-1 flex-col justify-center gap-6 px-6 py-16">
      <div>
        <h1 className="text-3xl font-semibold">AI Data Insight Engine</h1>
        <p className="mt-2 text-sm opacity-70">
          Upload your dataset and get a data analyst&apos;s first 30 minutes of analysis instantly.
        </p>
      </div>

      <div className="rounded-lg border border-black/10 p-4 text-sm dark:border-white/15">
        <div className="font-medium">Backend</div>
        <div className="mt-1 font-mono text-xs opacity-70">{API_URL}</div>
        <div className="mt-3">
          {status.state === "loading" && <span className="opacity-70">Checking connection…</span>}
          {status.state === "connected" && (
            <span className="text-green-600 dark:text-green-400">Connected — {status.app}</span>
          )}
          {status.state === "error" && (
            <span className="text-red-600 dark:text-red-400">Not reachable — {status.message}</span>
          )}
        </div>
      </div>
    </main>
  );
}
