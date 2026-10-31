import type { ProductColour } from "../lib/api";
import { QR_PATH, QR_SIZE } from "./qrArt";

/** The four tag colours. `body` is the tag itself; `ink` is the printed wordmark. */
export const TAG_COLOURS: Record<ProductColour, { body: string; edge: string; ink: string; name: string }> = {
  BLACK: { body: "#0A0A0A", edge: "#2E2E2E", ink: "#F5F1E8", name: "Black" },
  IVORY: { body: "#F5F1E8", edge: "#D9D0BC", ink: "#0A0A0A", name: "Ivory" },
  BURGUNDY: { body: "#74152B", edge: "#93334A", ink: "#F5F1E8", name: "Burgundy" },
  GLACIER: { body: "#B7D5E5", edge: "#98BACD", ink: "#10303F", name: "Glacier" },
};

/**
 * The CARTAG tag, drawn in SVG. The pattern is a real QR code (for a made-up tag code),
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
  // The QR sits on a light plate whatever the colour of the tag, so it always looks scannable.
  const plate = { x: 38, y: 92, size: 144 };
  const pad = 14;
  const scale = (plate.size - pad * 2) / QR_SIZE;

  return (
    <svg
      viewBox="0 0 220 300"
      role={title ? "img" : "presentation"}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      className={className}
    >
      <defs>
        <linearGradient id={`${id}-sheen`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity={colour === "BLACK" ? 0.1 : 0.34} />
          <stop offset="0.55" stopColor="#fff" stopOpacity="0" />
          <stop offset="1" stopColor="#000" stopOpacity={colour === "BLACK" ? 0.25 : 0.1} />
        </linearGradient>
        {shadow && (
          <filter id={`${id}-shadow`} x="-20%" y="-10%" width="140%" height="130%">
            <feDropShadow dx="0" dy="10" stdDeviation="9" floodColor="#0a0a0a" floodOpacity="0.26" />
          </filter>
        )}
      </defs>
      <g filter={shadow ? `url(#${id}-shadow)` : undefined}>
        <rect x="10" y="8" width="200" height="284" rx="30" fill={c.body} />
        <rect x="10" y="8" width="200" height="284" rx="30" fill={`url(#${id}-sheen)`} />
        <rect x="11.5" y="9.5" width="197" height="281" rx="28.5" fill="none" stroke={c.edge} strokeWidth="1.5" />
      </g>
      {/* the hole for a key ring or lanyard */}
      <circle cx="110" cy="44" r="12" fill="none" stroke={c.edge} strokeWidth="1.5" />
      <circle cx="110" cy="44" r="9.5" style={{ fill: "var(--c-bg)" }} />
      {/* QR plate */}
      <rect x={plate.x} y={plate.y} width={plate.size} height={plate.size} rx="16" fill="#F5F1E8" />
      <g transform={`translate(${plate.x + pad} ${plate.y + pad}) scale(${scale})`}>
        <path d={QR_PATH} fill="#0A0A0A" shapeRendering="crispEdges" />
      </g>
      <text
        x="110"
        y="266"
        textAnchor="middle"
        fill={c.ink}
        style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontStretch: "125%", letterSpacing: "0.14em", fontSize: 19 }}
      >
        CARTAG
      </text>
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
