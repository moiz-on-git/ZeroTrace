/**
 * Portal internationalisation.
 *
 * Five principal-facing languages load as flat-bundle resources (keySeparator
 * off — the keys themselves contain dots, e.g. "portal.receipt.title"). The
 * chosen language swaps t() output AND the portal's script face; console
 * screens stay English (their audience is the DPO, not the principal).
 *
 * Script fonts (Noto Sans Devanagari/Kannada/Tamil/Telugu) are loaded on
 * demand — one dynamic CSS import per script — and cached in-module, so a
 * bilingual visitor pays for at most two Unicode planes.
 */
import i18next from "i18next";
import { initReactI18next } from "react-i18next";

import deTaggedEn from "./en.json";
import deTaggedHi from "./hi.json";
import deTaggedKn from "./kn.json";
import deTaggedTa from "./ta.json";
import deTaggedTe from "./te.json";

export type PortalScript = "latin" | "devanagari" | "kannada" | "tamil" | "telugu";

export interface PortalLocale {
  /** BCP-47 tag, also sent upstream as the `language_hint` intake field. */
  code: string;
  /** Resource bundle key. */
  id: string;
  /** Native endonym — rendered in that script's own face. */
  native: string;
  script: PortalScript;
}

export const PORTAL_LOCALES: readonly PortalLocale[] = [
  { code: "en-IN", id: "en", native: "English", script: "latin" },
  { code: "hi-IN", id: "hi", native: "हिन्दी", script: "devanagari" },
  { code: "kn-IN", id: "kn", native: "ಕನ್ನಡ", script: "kannada" },
  { code: "ta-IN", id: "ta", native: "தமிழ்", script: "tamil" },
  { code: "te-IN", id: "te", native: "తెలుగు", script: "telugu" },
];

export const DEFAULT_LOCALE: PortalLocale = { code: "en-IN", id: "en", native: "English", script: "latin" };

const STORAGE_KEY = "zt.portal.lang";
const FALLBACK = "en-IN";

function storedLocale(): string {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    if (v && PORTAL_LOCALES.some((l) => l.code === v)) return v;
  } catch {
    /* private mode — the choice degrades to session-only */
  }
  return FALLBACK;
}

void i18next.use(initReactI18next).init({
  lng: storedLocale(),
  fallbackLng: FALLBACK,
  resources: {
    "en-IN": { translation: deTaggedEn },
    "hi-IN": { translation: deTaggedHi },
    "kn-IN": { translation: deTaggedKn },
    "ta-IN": { translation: deTaggedTa },
    "te-IN": { translation: deTaggedTe },
  },
  keySeparator: false, // flat keys like "portal.verify.body"
  nsSeparator: false,
  interpolation: { escapeValue: false }, // react escapes already
  returnEmptyString: false,
});

/* ---------- script fonts (dynamic CSS imports, loaded once per session) ---------- */

const SCRIPT_CSS: Record<Exclude<PortalScript, "latin">, () => Promise<unknown>> = {
  devanagari: () => import("@fontsource/noto-sans-devanagari/index.css"),
  kannada: () => import("@fontsource/noto-sans-kannada/index.css"),
  tamil: () => import("@fontsource/noto-sans-tamil/index.css"),
  telugu: () => import("@fontsource/noto-sans-telugu/index.css"),
};

const loadedScripts = new Set<string>(["latin"]);

function loadScriptCss(script: PortalScript): Promise<unknown> {
  if (script === "latin" || loadedScripts.has(script)) return Promise.resolve();
  loadedScripts.add(script);
  return SCRIPT_CSS[script]();
}

/** Applies a locale end to end: persists it, switches i18next, loads the
 *  matching script face. Resolves with the canonical locale record. */
export async function applyLocale(code: string): Promise<PortalLocale> {
  const loc = PORTAL_LOCALES.find((l) => l.code === code) ?? DEFAULT_LOCALE;
  try {
    window.localStorage.setItem(STORAGE_KEY, loc.code);
  } catch {
    /* private mode */
  }
  if (i18next.language !== loc.code) await i18next.changeLanguage(loc.code);
  await loadScriptCss(loc.script);
  return loc;
}

/** Pre-loads every script face at once — the portal renders all five endonym
 *  chips at all times, so each needs its @font-face declared. */
export function loadAllScriptFonts(): void {
  for (const loc of PORTAL_LOCALES) void loadScriptCss(loc.script);
}

export default applyLocale;
