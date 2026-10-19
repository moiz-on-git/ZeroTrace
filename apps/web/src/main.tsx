import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "@/App";
import "@/styles/index.css";
import "@/i18n";
import { env } from "@/lib/env";

async function boot(): Promise<void> {
  if (env.useMock) {
    // MSW is mock-mode-only: dynamic import keeps it out of the production
    // entry chunk entirely.
    const { startMockWorker } = await import("@/mocks/browser");
    await startMockWorker().catch((err: unknown) => {
      // The app degrades to proxy routing if the worker is unavailable — never
      // a silent failure for the demo operator.
      console.warn("MSW unavailable, continuing unmocked:", err);
    });
  }
  const el = document.getElementById("root");
  if (!el) throw new Error("#root missing");
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: 2,
        refetchOnWindowFocus: false,
        staleTime: 3_000,
        gcTime: 10 * 60_000,
      },
    },
  });
  ReactDOM.createRoot(el).render(
    <React.StrictMode>
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>
    </React.StrictMode>
  );
}

void boot();
