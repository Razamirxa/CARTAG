import { StrictMode } from "react";
import { createRoot, hydrateRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import App, { makeQueryClient } from "./App";
import "./index.css";

const root = document.getElementById("root")!;
// Home and Shop arrive as finished HTML (see scripts/prerender.mjs); every other page starts empty.
const hydrating = root.hasChildNodes();
const app = (
  <StrictMode>
    <BrowserRouter>
      <App queryClient={makeQueryClient()} hydrating={hydrating} />
    </BrowserRouter>
  </StrictMode>
);

if (hydrating) hydrateRoot(root, app);
else createRoot(root).render(app);
