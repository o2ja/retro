import { InquiryForm } from "@/components/inquiry";
import { getProducts, getSiteSettings, getSocialLinks, isSold } from "@/lib/api";
import type { ProductSummary, SocialLink } from "@/lib/types";

export const metadata = {
  title: "Contact",
  description: "Speak to Retro Watches about a watch, or ask us to find one.",
};

export default async function ContactPage(props: PageProps<"/contact">) {
  const { watch } = await props.searchParams;
  const [settings, socialLinks, products] = await Promise.all([
    getSiteSettings().catch(() => null),
    getSocialLinks().catch(() => [] as SocialLink[]),
    getProducts({ page_size: 60 })
      .then((page) => page.items)
      .catch(() => [] as ProductSummary[]),
  ]);

  const email = settings?.contact_email;
  const phone = settings?.contact_phone;

  return (
    <div className="shell grid gap-16 pt-32 pb-section sm:pt-40 lg:grid-cols-12 lg:gap-6">
      <div className="lg:col-span-5">
        <h1 className="text-[clamp(3rem,1.8rem+5vw,6.5rem)] leading-[0.92] tracking-[-0.03em]">
          <span className="rise">
            <span>Speak with</span>
          </span>
          <span className="rise">
            <span style={{ "--delay": "110ms" } as React.CSSProperties}>
              the store
            </span>
          </span>
        </h1>
        <p className="fade-in mt-8 max-w-sm text-ink-muted" style={{ "--delay": "300ms" } as React.CSSProperties}>
          Buying, selling, or searching for a particular reference: leave your details and you will hear back
          from a person, not a system.
        </p>

        <dl className="fade-in mt-14 space-y-6 border-t border-line pt-8" style={{ "--delay": "450ms" } as React.CSSProperties}>
          {email && <Channel label="Email" value={email} href={`mailto:${email}`} />}
          {phone && <Channel label="Telephone" value={phone} href={`tel:${phone.replace(/[^\d+]/g, "")}`} />}
          {socialLinks.map((link) => (
            <Channel key={link.platform} label={link.platform} value={link.label ?? link.url} href={link.url} external />
          ))}
          {settings?.address && (
            <div>
              <dt className="eyebrow">Address</dt>
              <dd className="mt-1.5 text-lg">{settings.address}</dd>
            </div>
          )}
        </dl>
      </div>

      <div className="lg:col-span-6 lg:col-start-7">
        <div className="bg-surface-muted px-6 py-10 sm:px-12 sm:py-14">
          <h2 className="mb-10 text-[2rem] leading-tight sm:text-[2.4rem]">Make an inquiry</h2>
          <InquiryForm
            choices={products.filter((product) => !isSold(product))}
            initialChoice={typeof watch === "string" ? watch : ""}
            storePhone={phone ?? null}
            submitLabel="Send inquiry"
          />
        </div>
      </div>
    </div>
  );
}

function Channel({
  label,
  value,
  href,
  external = false,
}: {
  label: string;
  value: string;
  href: string;
  external?: boolean;
}) {
  return (
    <div>
      <dt className="eyebrow">{label}</dt>
      <dd className="mt-1.5">
        <a
          href={href}
          {...(external ? { target: "_blank", rel: "noreferrer noopener" } : {})}
          className="link-line text-lg"
        >
          {value}
        </a>
      </dd>
    </div>
  );
}
