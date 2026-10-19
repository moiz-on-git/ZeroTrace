import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});

/* jsdom lacks structuredClone semantics parity in older builds; Vitest's node
   runtime provides it, but keep a guard identical in behaviour */
if (typeof globalThis.structuredClone !== "function") {
  globalThis.structuredClone = (v: unknown) => (v === undefined ? v : JSON.parse(JSON.stringify(v)));
}

vi.useFakeTimers({ shouldAdvanceTime: true });
