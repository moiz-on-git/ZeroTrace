/** Typed API client. Parses the response envelope, validates payloads with
 *  zod at the boundary, attaches the JWT and idempotency keys, and surfaces
 *  typed errors with the machine code visible (§ quality rules). */
import { env, demoUpstream } from "@/lib/env";
import type { Envelope } from "./schemas";
import { envelopeZ, type ApiErrorCode } from "./schemas";

export class ApiError extends Error {
  readonly code: ApiErrorCode | string;
  readonly details: unknown;
  readonly requestId?: string;
  readonly status: number;

  constructor(status: number, code: ApiErrorCode | string, message: string, details: unknown, requestId?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

const TOKEN_KEY = "zt.demo.jwt";

export const authStore = {
  token(): string | null {
    // Demo JWT only; the receipt secret is never persisted (kept in memory).
    try {
      return window.sessionStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string): void {
    try {
      window.sessionStorage.setItem(TOKEN_KEY, token);
    } catch {
      /* private mode — auth demotes to anonymous dpo runs */
    }
  },
  clear(): void {
    try {
      window.sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      /* noop */
    }
  },
};

/** ULID-shaped request identifiers (client-generated correlation IDs). */
export function requestId(prefix: string): string {
  const time = Date.now().toString(36).toUpperCase().padStart(10, "0").slice(-10);
  const rand = Math.ceil(Math.random() * 2 ** 48)
    .toString(36)
    .toUpperCase()
    .padStart(10, "0")
    .slice(-10)
    .replace(/[ILUO]/g, () => Math.ceil(Math.random() * 9).toString());
  return `${prefix}_${time}${rand}`;
}

function full(path: string): string {
  return path.startsWith("http") ? path : `${env.apiBase}${path}`;
}

async function request<T>(method: string, path: string, schema: { parse(v: unknown): T }, body?: unknown, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    // demo degradation flag; the mock layer translates it to UPSTREAM_UNAVAILABLE
    "x-zt-demo-upstream": demoUpstream.get(),
  };
  if (method !== "GET") headers["Idempotency-Key"] = requestId("idem");
  // FormData sets its own multipart Content-Type + boundary.
  if (body !== undefined && !(body instanceof FormData)) headers["Content-Type"] = "application/json";
  const token = authStore.token();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(full(path), {
    method,
    headers,
    body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
    signal: AbortSignal.timeout(20_000),
    ...init,
  });

  let payload: unknown;
  try {
    payload = await res.json();
  } catch {
    throw new ApiError(res.status, "INTERNAL", `Non-JSON response from ${path} (HTTP ${res.status})`, null);
  }

  const env_parsed = envelopeZ.parse(payload) as Envelope<T>;
  if (res.status >= 400 || env_parsed.error) {
    const err = env_parsed.error;
    throw new ApiError(
      res.status,
      err?.code ?? "INTERNAL",
      err?.message ?? `Request failed (HTTP ${res.status})`,
      err?.details,
      env_parsed.request_id
    );
  }
  return schema.parse(env_parsed.data);
}

export const api = {
  get: <T>(path: string, schema: { parse(v: unknown): T }) => request("GET", path, schema),
  post: <T>(path: string, schema: { parse(v: unknown): T }, body?: unknown) => request("POST", path, schema, body),
  /** multipart (voice intake: audio blob + language hint). */
  postForm: <T>(path: string, schema: { parse(v: unknown): T }, form: FormData) =>
    request("POST", path, schema, form),
};
