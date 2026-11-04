import type { ProductColour } from "../lib/api";
import { QR_PATH, QR_SIZE } from "./qrArt";
import { CONTACT, LOGO_CAR, LOGO_TAG, SCAN } from "./tagText";

/**
 * The four tag colours, the same as the print files (cartag/qr/tag_art.py). `body` is the tag, `ink` the
 * text and QR, `accent` the corner mark and `edge` the outline of a colour chip.
 */
export const TAG_COLOURS: Record<ProductColour, { body: string; ink: string; accent: string; edge: string; name: string }> = {
  BLACK: { body: "#0D0D0D", ink: "#FAFAFA", accent: "#C4FA1C", edge: "#2E2E2E", name: "Black" },
  IVORY: { body: "#F9F6F1", ink: "#0A0A0A", accent: "#D20C1E", edge: "#D9D0BC", name: "Ivory" },
  BURGUNDY: { body: "#47031C", ink: "#FAFAFA", accent: "#F7F7F7", edge: "#6B1F37", name: "Burgundy" },
  GLACIER: { body: "#BBD0E3", ink: "#0A0A0A", accent: "#7194B2", edge: "#9FB3C8", name: "Glacier" },
};

// The tag geometry on a 100 x 100 grid, as in the print files: corner radius 13.5, the QR 41 wide.
const RADIUS = 13.5;
const QR = { left: 29.5, top: 32.3, width: 41 };
/** The corner mark, copied from _accent_ops in cartag/qr/tag_art.py: inset 3 from the edges, ends rounded. */
const ACCENT_PATH =
  "M83 3L86.5 3C92.299 3 97 7.701 97 13.5L97 18.6C97 19.533 96.687 19.654 96.06 18.962L82.54 4.038C81.913 3.346 82.067 3 83 3Z";

/**
 * The CARTAG tag as it is printed. The pattern is a real QR code (for a made-up tag code),
 * so the picture is the product and not a stand-in for it.
 */
export function TagArt({
  colour,
  className,
  title,
  shadow = true,
}: {
  colour: ProductColour;
  className?: string;
  title?: string;
  shadow?: boolean;
}) {
  const c = TAG_COLOURS[colour];
  const id = `tag-${colour}`;

  return (
    <svg
      viewBox="-6 -4 112 114"
      role={title ? "img" : "presentation"}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      className={className}
    >
      <defs>
        <clipPath id={`${id}-shape`}>
          <rect width="100" height="100" rx={RADIUS} />
        </clipPath>
        <linearGradient id={`${id}-sheen`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity={colour === "BLACK" ? 0.08 : 0.22} />
          <stop offset="0.55" stopColor="#fff" stopOpacity="0" />
          <stop offset="1" stopColor="#000" stopOpacity={colour === "BLACK" ? 0.2 : 0.08} />
        </linearGradient>
        {shadow && (
          <filter id={`${id}-shadow`} x="-20%" y="-15%" width="140%" height="140%">
            <feDropShadow dx="0" dy="4" stdDeviation="3.5" floodColor="#0a0a0a" floodOpacity="0.26" />
          </filter>
        )}
      </defs>
      <rect width="100" height="100" rx={RADIUS} fill={c.body} filter={shadow ? `url(#${id}-shadow)` : undefined} />
      <g clipPath={`url(#${id}-shape)`}>
        <path d={ACCENT_PATH} fill={c.accent} />
        <g fill={c.ink}>
          <path d={LOGO_CAR} />
          <path d={LOGO_TAG} />
          <path d={CONTACT} />
          <path d={SCAN} />
        </g>
        <g transform={`translate(${QR.left} ${QR.top}) scale(${QR.width / QR_SIZE})`}>
          <path d={QR_PATH} fill={c.ink} shapeRendering="crispEdges" />
        </g>
        <rect width="100" height="100" fill={`url(#${id}-sheen)`} />
      </g>
    </svg>
  );
}

/** The CARTAG wordmark from the tag: heavy CAR, light TAG. It takes the text colour. */
export function Wordmark({ className }: { className?: string }) {
  return (
    <svg viewBox="18.6 16.9 62.2 9.1" className={className} fill="currentColor" aria-hidden="true">
      <path d={LOGO_CAR} />
      <path d={LOGO_TAG} />
    </svg>
  );
}

/** Small round colour chip used in pickers. */
export function Swatch({ colour, selected, onClick, label }: { colour: ProductColour; selected?: boolean; onClick?: () => void; label?: string }) {
  const c = TAG_COLOURS[colour];
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label ?? c.name}
      aria-pressed={selected}
      className="inline-flex size-11 items-center justify-center rounded-full"
    >
      <span
        className="block size-8 rounded-full transition-transform"
        style={{
          background: c.body,
          boxShadow: selected ? `0 0 0 2px var(--c-surface), 0 0 0 4px var(--c-brand)` : `inset 0 0 0 1.5px ${c.edge}`,
          transform: selected ? "scale(1.06)" : undefined,
        }}
      />
    </button>
  );
}
