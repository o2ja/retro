"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Banner, Field } from "@/components/admin/ui";
import { adminLogin } from "@/lib/admin";
import { ApiError } from "@/lib/api";

export default function AdminLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    adminLogin(email, password)
      .then(() => router.push("/admin"))
      .catch((cause: unknown) => {
        // The server returns one message for every failure; it is not this
        // page's job to guess which part was wrong.
        setError(
          cause instanceof ApiError ? cause.message : "Could not sign in.",
        );
        setBusy(false);
      });
  }

  return (
    <div className="grid min-h-screen place-items-center px-5">
      <div className="w-full max-w-sm">
        <p className="font-display text-xl tracking-[0.12em] uppercase">Retro Watches</p>
        <h1 className="mt-1 mb-8 text-2xl">Administration</h1>

        {error && <Banner kind="error">{error}</Banner>}

        <form onSubmit={handleSubmit} className="space-y-4">
          <Field label="Email">
            <input
              type="email"
              required
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="field"
            />
          </Field>
          <Field label="Password">
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="field"
            />
          </Field>
          <button type="submit" disabled={busy} className="btn btn-primary w-full">
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="mt-6 text-xs text-ink-subtle">
          Repeated failed attempts are rate limited.
        </p>
      </div>
    </div>
  );
}
