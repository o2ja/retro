import { Collection } from "@/components/collection";
import { getCollection } from "@/lib/api";

export const metadata = {
  title: "The collection",
  description: "Every watch held by Retro Watches, each photographed and described as it is.",
};

export default async function ShopPage(props: PageProps<"/shop">) {
  const { category } = await props.searchParams;
  const collection = await getCollection().catch(() => null);

  return (
    <div className="shell pt-32 pb-section sm:pt-40">
      <header className="mb-14 grid gap-8 sm:mb-20 lg:grid-cols-12 lg:items-end">
        <h1 className="text-[clamp(3rem,1.8rem+5.4vw,7.5rem)] leading-[0.92] tracking-[-0.03em] lg:col-span-8">
          <span className="rise">
            <span>The collection</span>
          </span>
        </h1>
        <p
          className="fade-in max-w-sm text-ink-muted lg:col-span-4 lg:pb-3"
          style={{ "--delay": "300ms" } as React.CSSProperties}
        >
          Each piece is held by us, described as it is, and photographed as it arrived. Choose one and request
          it; the store will call you.
        </p>
      </header>

      {collection ? (
        <Collection
          products={collection.products}
          categories={collection.categories}
          initialCategory={typeof category === "string" ? category : ""}
          syncUrl
        />
      ) : (
        <p role="alert" className="py-20 text-ink-muted">
          The collection could not be loaded just now. Please try again in a moment.
        </p>
      )}
    </div>
  );
}
