/**
 * MSW worker bootstrap (mock mode). Intercepted requests answer from the
 * generated fixtures, including the §7.2 SSE endpoint via MSW's stream API.
 */
import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

export async function startMockWorker(): Promise<void> {
  // mocked mode needs the service worker asset: public/mockServiceWorker.js
  await setupWorker(...handlers).start({
    onUnhandledFrame: "warn",
    quiet: false,
  });
}
