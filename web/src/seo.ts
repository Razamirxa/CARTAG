/**
 * What search engines and link previews see. The pages listed in PRERENDERED_PAGES are turned into
 * finished HTML at build time (scripts/prerender.mjs) and listed in the sitemap; everything else is
 * behind a login and is not meant to be found.
 */
export interface PageMeta {
  title: string;
  description: string;
}

const PAGES: Record<string, PageMeta> = {
  "/": {
    title: "CARTAG | A QR tag so anyone can reach you about your car or bike",
    description:
      "Put a CARTAG on your car or bike. Whoever scans it can call you or message you on WhatsApp, and your number is never printed on the page.",
  },
  "/shop": {
    title: "Shop CARTAG tags | Three sizes, four colours",
    description:
      "Order a CARTAG QR tag for your car or bike in Compact, Standard or Large, in Black, Ivory, Burgundy or Glacier. Turn it on with your phone when it arrives.",
  },
};

export const PRERENDERED_PAGES = Object.keys(PAGES);

const DEFAULT: PageMeta = { title: "CARTAG", description: PAGES["/"]!.description };

export function pageMeta(pathname: string): PageMeta {
  return PAGES[pathname.replace(/\/+$/, "") || "/"] ?? DEFAULT;
}
