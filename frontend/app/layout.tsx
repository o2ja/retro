import type { Metadata, Viewport } from "next";
import { Bodoni_Moda, Jost } from "next/font/google";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { Motion } from "@/components/motion";
import { getSiteSettings, getSocialLinks } from "@/lib/api";
import type { SiteSettings, SocialLink } from "@/lib/types";

import "./globals.css";

// Two families: a high-contrast Didone for names and headlines, a geometric
// sans for everything a customer reads or taps.
const display = Bodoni_Moda({
  variable: "--font-bodoni",
  subsets: ["latin"],
  style: ["normal", "italic"],
  display: "swap",
});

const sans = Jost({
  variable: "--font-jost",
  subsets: ["latin"],
  weight: ["300", "400", "500"],
  display: "swap",
});

/** The whole chrome is CMS-driven, so one failed call must not blank the site. */
async function loadChrome(): Promise<{
  settings: SiteSettings | null;
  socialLinks: SocialLink[];
}> {
  const [settings, socialLinks] = await Promise.all([
    getSiteSettings().catch(() => null),
    getSocialLinks().catch(() => []),
  ]);
  return { settings, socialLinks };
}

export const viewport: Viewport = {
  themeColor: "#0a0a0a",
};

export async function generateMetadata(): Promise<Metadata> {
  const settings = await getSiteSettings().catch(() => null);
  const brand = settings?.brand_name ?? "Retro Watches";
  return {
    title: {
      default: settings?.seo_title ?? brand,
      template: `%s | ${brand}`,
    },
    description: settings?.seo_description ?? settings?.tagline ?? undefined,
    openGraph: {
      title: settings?.seo_title ?? brand,
      description: settings?.seo_description ?? undefined,
      siteName: brand,
      type: "website",
    },
  };
}

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const { settings, socialLinks } = await loadChrome();
  const instagram = socialLinks.find((link) => link.platform === "instagram") ?? null;

  return (
    <html lang="en" className={`${display.variable} ${sans.variable} h-full`}>
      <body className="flex min-h-full flex-col">
        <Motion />
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[60] focus:bg-surface focus:px-4 focus:py-2"
        >
          Skip to content
        </a>
        <SiteHeader brandName={settings?.brand_name ?? "Retro Watches"} instagram={instagram} />
        <main id="main" className="flex-1">
          {children}
        </main>
        <SiteFooter settings={settings} socialLinks={socialLinks} />
      </body>
    </html>
  );
}
