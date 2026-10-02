"use client";

import { useEffect, useState } from "react";

import { AccountForm } from "@/components/AccountForm";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Workspace, rememberDataset } from "@/components/Workspace";
import { fetchAccount, logOut, type Account } from "@/lib/api";

export default function Home() {
  // undefined while the page asks who is signed in, null when nobody is.
  const [account, setAccount] = useState<Account | null | undefined>(undefined);

  useEffect(() => {
    fetchAccount()
      .then(setAccount)
      .catch(() => setAccount(null));
  }, []);

  async function signOut() {
    try {
      await logOut();
    } finally {
      // The next account to log in here must not be sent to this one's dataset. A
      // session that merely expired keeps it, so logging back in reopens it.
      rememberDataset(null);
      setAccount(null);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-6 py-12">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">DataSight</h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Upload a dataset and get a data analyst&apos;s first pass over it.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {account && (
            <>
              <span className="text-sm text-[var(--text-secondary)]">{account.username}</span>
              <button
                type="button"
                onClick={signOut}
                className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm"
              >
                Log out
              </button>
            </>
          )}
          <ThemeToggle />
        </div>
      </header>

      {account === null && <AccountForm onSignedIn={setAccount} />}
      {account && (
        // Keyed by account, so nothing one reader had open is left for the next.
        <Workspace key={account.username} onSignedOut={() => setAccount(null)} />
      )}
    </main>
  );
}
