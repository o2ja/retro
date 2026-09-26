"use client";

export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="shell flex min-h-[80svh] flex-col items-start justify-center pt-32 pb-section">
      <h1 className="text-[clamp(2.5rem,1.6rem+3.6vw,5rem)] leading-[0.95]">Something went wrong.</h1>
      <p className="mt-6 max-w-md text-ink-muted">The page could not be loaded. This is usually temporary.</p>
      <button type="button" onClick={reset} className="btn btn-secondary mt-10">
        Try again
      </button>
    </div>
  );
}
