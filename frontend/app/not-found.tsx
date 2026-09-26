import Link from "next/link";

export default function NotFound() {
  return (
    <div className="shell flex min-h-[80svh] flex-col items-start justify-center pt-32 pb-section">
      <p className="eyebrow">Not found</p>
      <h1 className="mt-6 max-w-3xl text-[clamp(2.75rem,1.6rem+4.6vw,6rem)] leading-[0.95]">
        This piece has moved on.
      </h1>
      <p className="mt-6 max-w-md text-ink-muted">The page or watch you were looking for is no longer here.</p>
      <Link href="/shop" className="btn btn-primary mt-10">
        See the collection
      </Link>
    </div>
  );
}
