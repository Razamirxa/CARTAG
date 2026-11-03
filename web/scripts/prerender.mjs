// Runs after `vite build`: turns the public pages (Home and Shop) into finished HTML, so search engines
// and link previews get the full text without running JavaScript. The browser then takes the page over.
// The server fills in __PUBLIC_BASE_URL__ when it sends the page (cartag/main.py).
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(web, "dist");
const ssr = join(web, ".ssr");
const { render, pageMeta, PRERENDERED_PAGES } = await import(pathToFileURL(join(ssr, "entry-server.js")).href);

const shell = await readFile(join(dist, "index.html"), "utf8");
// Every page that is not pre-rendered gets the empty shell.
await writeFile(join(dist, "app.html"), shell);

const escape = (text) => text.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function swap(html, pattern, replacement) {
  if (!pattern.test(html)) throw new Error(`prerender: ${pattern} not found in index.html`);
  return html.replace(pattern, replacement);
}

for (const path of PRERENDERED_PAGES) {
  const { title, description } = pageMeta(path);
  const url = `__PUBLIC_BASE_URL__${path}`;
  const head = [
    `<meta name="description" content="${escape(description)}" />`,
    `<link rel="canonical" href="${url}" />`,
    `<meta property="og:type" content="website" />`,
    `<meta property="og:site_name" content="CARTAG" />`,
    `<meta property="og:title" content="${escape(title)}" />`,
    `<meta property="og:description" content="${escape(description)}" />`,
    `<meta property="og:url" content="${url}" />`,
    `<meta property="og:image" content="__PUBLIC_BASE_URL__/og-image.png" />`,
    `<meta property="og:image:width" content="1200" />`,
    `<meta property="og:image:height" content="630" />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
  ].join("\n    ");

  let html = swap(shell, /<title>[^<]*<\/title>/, `<title>${escape(title)}</title>`);
  html = swap(html, /<meta name="description" content="[^"]*"\s*\/?>/, head);
  html = swap(html, /<div id="root"><\/div>/, `<div id="root">${await render(path)}</div>`);

  const out = path === "/" ? join(dist, "index.html") : join(dist, path.slice(1), "index.html");
  await mkdir(dirname(out), { recursive: true });
  await writeFile(out, html);
}

await rm(ssr, { recursive: true, force: true });
