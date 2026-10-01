"use client";

import { useEffect, useState, type FormEvent } from "react";

import {
  PROVIDER_NAMES,
  fetchSignInOptions,
  logIn,
  signInUrl,
  signUp,
  type Account,
  type Provider,
} from "@/lib/api";

type Props = {
  onSignedIn: (account: Account) => void;
};

/**
 * Why a sign-in at Google or GitHub came back without signing in. The API puts it
 * in the address: ?signin=cancelled|failed&with=google|github.
 */
function signInProblem(): string | null {
  if (typeof window === "undefined") return null;
  const query = new URLSearchParams(window.location.search);
  const problem = query.get("signin");
  if (!problem) return null;
  const name = PROVIDER_NAMES[query.get("with") as Provider] ?? "that account";
  return problem === "cancelled"
    ? `Signing in with ${name} was cancelled.`
    : `Signing in with ${name} did not work. Try again, or use a password.`;
}

const INPUT_CLASS =
  "w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm";

export function AccountForm({ onSignedIn }: Props) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(signInProblem);
  const [providers, setProviders] = useState<Provider[]>([]);
  const isSignUp = mode === "signup";

  useEffect(() => {
    fetchSignInOptions()
      .then((options) =>
        setProviders((Object.keys(PROVIDER_NAMES) as Provider[]).filter((name) => options[name])),
      )
      .catch(() => setProviders([]));

    // Said once: a reload should not repeat it.
    const address = new URL(window.location.href);
    if (address.searchParams.has("signin")) {
      address.searchParams.delete("signin");
      address.searchParams.delete("with");
      window.history.replaceState(null, "", address);
    }
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsBusy(true);
    setError(null);
    try {
      onSignedIn(await (isSignUp ? signUp : logIn)(username.trim(), password));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "That did not work.");
      setIsBusy(false);
    }
  }

  return (
    <section className="mx-auto w-full max-w-sm rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
      <h2 className="text-lg font-semibold">{isSignUp ? "Create an account" : "Log in"}</h2>
      <p className="mt-1 text-sm text-[var(--text-secondary)]">
        {isSignUp
          ? "Your datasets are yours alone: nobody else signed in can see them."
          : "Log in to upload and explore your datasets."}
      </p>

      {providers.length > 0 && (
        <>
          <div className="mt-5 flex flex-col gap-2">
            {providers.map((name) => (
              <a
                key={name}
                href={signInUrl(name)}
                className="flex w-full items-center justify-center rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium"
              >
                Continue with {PROVIDER_NAMES[name]}
              </a>
            ))}
          </div>
          <div className="mt-5 flex items-center gap-3 text-xs text-[var(--text-muted)]">
            <span className="h-px flex-1 bg-[var(--border)]" />
            or with a username
            <span className="h-px flex-1 bg-[var(--border)]" />
          </div>
        </>
      )}

      <form onSubmit={submit} className="mt-5 flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Username</span>
          <input
            className={INPUT_CLASS}
            name="username"
            autoComplete="username"
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </label>
        <div className="flex flex-col gap-1 text-sm">
          <label className="flex flex-col gap-1">
            <span className="font-medium">Password</span>
            <input
              className={INPUT_CLASS}
              name="password"
              type="password"
              autoComplete={isSignUp ? "new-password" : "current-password"}
              required
              minLength={isSignUp ? 8 : undefined}
              aria-describedby={isSignUp ? "password-rule" : undefined}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {isSignUp && (
            <span id="password-rule" className="text-xs text-[var(--text-muted)]">
              At least 8 characters.
            </span>
          )}
        </div>

        {error && <p className="text-sm text-[var(--flag-warning)]">{error}</p>}

        <button
          type="submit"
          disabled={isBusy}
          className="rounded-lg bg-[var(--foreground)] px-4 py-2 text-sm font-medium text-[var(--background)] disabled:opacity-50"
        >
          {isBusy ? "One moment…" : isSignUp ? "Create account" : "Log in"}
        </button>
      </form>

      <p className="mt-4 text-sm text-[var(--text-secondary)]">
        {isSignUp ? "Already have an account?" : "New here?"}{" "}
        <button
          type="button"
          className="font-medium text-[var(--foreground)] underline underline-offset-2"
          onClick={() => {
            setMode(isSignUp ? "login" : "signup");
            setError(null);
          }}
        >
          {isSignUp ? "Log in" : "Create an account"}
        </button>
      </p>
    </section>
  );
}
