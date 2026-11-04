import type { ProductColour } from "../lib/api";
import { QR_PATH, QR_SIZE } from "./qrArt";
import { CONTACT, LOGO_CAR, LOGO_TAG, SCAN } from "./tagText";

type TagColour = {
  body: string;
  ink: string;
  accent: string;
  edge: string;
  name: string;
  side: string;
  bevel: [string, string];
  glow: string;
  shade: string;
  accentShade: string | null;
};

/**
 * The four tag colours, the same as the print files (cartag/qr/tag_art.py). `body` is the tag, `ink` the
 * text and QR, `accent` the corner mark and `edge` the outline of a colour chip. `side` is the band along
 * the bottom that shows the tag's thickness, `bevel` the bright rim round the face (top, bottom), `glow`
 * and `shade` the top and bottom of the face shading, and `accentShade` the dark end of the corner mark
 * (null where the corner is polished silver).
 */
export const TAG_COLOURS: Record<ProductColour, TagColour> = {
  BLACK: { body: "#0D0D0D", ink: "#FAFAFA", accent: "#C4FA1C", edge: "#2E2E2E", name: "Black", side: "#070707", bevel: ["#404040", "#272727"], glow: "#141414", shade: "#0B0B0B", accentShade: "#A1CD17" },
  IVORY: { body: "#F9F6F1", ink: "#0A0A0A", accent: "#D20C1E", edge: "#D9D0BC", name: "Ivory", side: "#EAE7E3", bevel: ["#FFFFFF", "#FBFAF9"], glow: "#F9F6F1", shade: "#F4F1EC", accentShade: "#AC0A19" },
  BURGUNDY: { body: "#47031C", ink: "#FAFAFA", accent: "#F7F7F7", edge: "#6B1F37", name: "Burgundy", side: "#120107", bevel: ["#89274B", "#611C35"], glow: "#501027", shade: "#3E0318", accentShade: null },
  GLACIER: { body: "#BBD0E3", ink: "#0A0A0A", accent: "#7194B2", edge: "#9FB3C8", name: "Glacier", side: "#83929F", bevel: ["#E9EEF2", "#D6DFE6"], glow: "#CFDEEB", shade: "#B7CCDE", accentShade: "#5D7992" },
};

/** Polished silver for Burgundy's corner, as offset and colour. */
const SILVER: [number, string][] = [
  [0, "#9C9C9E"],
  [0.35, "#E2E2E4"],
  [0.55, "#FFFFFF"],
  [0.75, "#F7F7F7"],
  [1, "#B9B9BB"],
];

// The tag geometry on a 100 x 100 grid, as in the print files: corner radius 13.5, the QR 41 wide, a
// 0.8 thickness band along the bottom, a 0.7 bevel round the face, all shading running straight down.
const RADIUS = 13.5;
const QR = { left: 29.5, top: 32.3, width: 41 };
const EDGE = 0.8;
const BEVEL = 0.7;
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
        <linearGradient id={`${id}-bevel`} gradientUnits="userSpaceOnUse" x1="50" y1="0" x2="50" y2="100">
          <stop offset="0" stopColor={c.bevel[0]} />
          <stop offset="1" stopColor={c.bevel[1]} />
        </linearGradient>
        <linearGradient id={`${id}-face`} gradientUnits="userSpaceOnUse" x1="50" y1="0" x2="50" y2="100">
          <stop offset="0" stopColor={c.glow} />
          <stop offset="0.5" stopColor={c.body} />
          <stop offset="1" stopColor={c.shade} />
        </linearGradient>
        <linearGradient id={`${id}-corner`} gradientUnits="userSpaceOnUse" x1="97" y1="3" x2="88.5" y2="12.2">
          {(c.accentShade ? ([[0, c.accentShade], [0.6, c.accent], [1, c.accent]] as [number, string][]) : SILVER).map(
            ([offset, color]) => (
              <stop key={offset} offset={offset} stopColor={color} />
            ),
          )}
        </linearGradient>
        {shadow && (
          <filter id={`${id}-shadow`} x="-20%" y="-15%" width="140%" height="140%">
            <feDropShadow dx="0" dy="4" stdDeviation="3.5" floodColor="#0a0a0a" floodOpacity="0.26" />
          </filter>
        )}
      </defs>
      <rect width="100" height="100" rx={RADIUS} fill={c.side} filter={shadow ? `url(#${id}-shadow)` : undefined} />
      <rect width="100" height={100 - EDGE} rx={RADIUS} fill={`url(#${id}-bevel)`} />
      <rect
        x={BEVEL}
        y={BEVEL}
        width={100 - 2 * BEVEL}
        height={100 - EDGE - 2 * BEVEL}
        rx={RADIUS - BEVEL}
        fill={`url(#${id}-face)`}
      />
      <g clipPath={`url(#${id}-shape)`}>
        <path d={ACCENT_PATH} fill={`url(#${id}-corner)`} />
        <g fill={c.ink}>
          <path d={LOGO_CAR} />
          <path d={LOGO_TAG} />
          <path d={CONTACT} />
          <path d={SCAN} />
        </g>
        <g transform={`translate(${QR.left} ${QR.top}) scale(${QR.width / QR_SIZE})`}>
          <path d={QR_PATH} fill={c.ink} shapeRendering="crispEdges" />
        </g>
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
