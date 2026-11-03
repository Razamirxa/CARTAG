import { StrictMode } from "react";
import { prerender } from "react-dom/static";
import { StaticRouter } from "react-router";
import App, { makeQueryClient } from "./App";

/** Renders one public page to HTML at build time, after every lazy page on it has loaded. */
export async function render(url: string): Promise<string> {
  const { prelude } = await prerender(
    <StrictMode>
      <StaticRouter location={url}>
        <App queryClient={makeQueryClient()} hydrating />
      </StaticRouter>
    </StrictMode>,
  );
  return new Response(prelude).text();
}

export { PRERENDERED_PAGES, pageMeta } from "./seo";
