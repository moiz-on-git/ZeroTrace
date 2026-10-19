/** Environment access. Every runtime knob is a VITE_* var (12-factor style). */

function str(name: keyof ImportMetaEnv, fallback = ""): string {
  const v = import.meta.env[name];
  return typeof v === "string" && v.length > 0 ? v : fallback;
}

export const env = {
  get apiBase(): string {
    // Default to the production Render orchestrator backend
    return str("VITE_API_BASE", "https://zerotrace-orchestrator.onrender.com");
  },
  get useMock(): boolean {
    const explicitlySet = str("VITE_USE_MOCK", "");
    if (explicitlySet !== "") {
      return explicitlySet.toLowerCase() === "true";
    }
    // Default to real backend execution (never fake/mock)
    return false;
  },
  get mockSpeed(): number {
    const n = Number(str("VITE_MOCK_SPEED", "1"));
    return Number.isFinite(n) && n > 0 ? n : 1;
  },
  get envLabel(): string {
    return str("VITE_ENV_LABEL", "local");
  },
  get explorerBase(): string {
    return str("VITE_EXPLORER_BASE", "https://sepolia.etherscan.io");
  },
  /** Pinned receipt-signer key. Empty falls back to the receipt's own key with
   *  a "self-attested" disclosure in the verifier. */
  get trustedSignerKey(): string {
    return str("VITE_TRUSTED_SIGNER_KEY", "");
  },
} as const;

/* ---------------------------------------------------------------- demo flags */
/* Presenter toggles that simulate upstream degradation. Transported via a
   request header so the MSW worker (separate context) can honour them; the
   flag itself lives in localStorage and is never read from the network. */

export type DemoUpstream = "ok" | "offline";

const UPSTREAM_KEY = "zt.demo.upstream";

export const demoUpstream = {
  get(): DemoUpstream {
    try {
      return window.localStorage.getItem(UPSTREAM_KEY) === "offline" ? "offline" : "ok";
    } catch {
      return "ok";
    }
  },
  set(v: DemoUpstream): void {
    try {
      window.localStorage.setItem(UPSTREAM_KEY, v);
    } catch {
      /* private mode — flag stays session-only */
    }
  },
};

