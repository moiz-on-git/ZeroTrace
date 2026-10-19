import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "./client";
import { z } from "zod";

const okZ = z.object({ hello: z.string() });

function fetchWith(payload: unknown, status = 200): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } }))
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.sessionStorage.clear();
});

describe("api client envelope handling", () => {
  it("unwraps §7.1 success envelope and validates the payload", async () => {
    fetchWith({ data: { hello: "world" }, error: null, request_id: "req_test_1" });
    const out = await api.get("/api/v1/x", okZ);
    expect(out).toEqual({ hello: "world" });
  });

  it("throws ApiError carrying the machine code from an error envelope", async () => {
    fetchWith(
      { data: null, error: { code: "NOT_FOUND", message: "job not found", details: null }, request_id: "req_test_2" },
      404
    );
    const err = await api.get("/api/v1/x", okZ).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    const apiErr = err as ApiError;
    expect(apiErr.code).toBe("NOT_FOUND");
    expect(apiErr.message).toBe("job not found");
    expect(apiErr.status).toBe(404);
    expect(apiErr.requestId).toBe("req_test_2");
  });

  it("treats error envelopes even on 200 as failures", async () => {
    fetchWith({ data: null, error: { code: "VERIFY_FAILED", message: "nope" }, request_id: "req_test_3" }, 200);
    const err = (await api.post("/api/v1/x", okZ, {}).catch((e: unknown) => e)) as ApiError;
    expect(err.code).toBe("VERIFY_FAILED");
  });

  it("fails loudly on non-JSON bodies", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("<html>gateway</html>", { status: 502 }))
    );
    const err = (await api.get("/api/v1/x", okZ).catch((e: unknown) => e)) as ApiError;
    expect(err.code).toBe("INTERNAL");
    expect(err.message).toContain("Non-JSON");
  });

  it("rejects payloads that break the zod schema at the boundary", async () => {
    fetchWith({ data: { hello: 42 }, error: null, request_id: "req_test_4" });
    await expect(api.get("/api/v1/x", okZ)).rejects.toThrow();
  });

  it("sends Authorization from the session store on every request", async () => {
    window.sessionStorage.setItem("zt.demo.jwt", "jwt_demo.abc");
    const f = vi.fn(async (..._a: unknown[]) => new Response(JSON.stringify({ data: { hello: "w" }, error: null }), { status: 200 }));
    vi.stubGlobal("fetch", f);
    await api.get("/api/v1/x", okZ);
    const init = f.mock.calls[0]?.[1] as RequestInit | undefined;
    const headers = new Headers(init?.headers as HeadersInit);
    expect(headers.get("Authorization")).toBe("Bearer jwt_demo.abc");
    expect(headers.get("Accept")).toBe("application/json");
  });

  it("attaches an idempotency key exactly on POST", async () => {
    const f = vi.fn(async (..._a: unknown[]) => new Response(JSON.stringify({ data: { hello: "w" }, error: null }), { status: 200 }));
    vi.stubGlobal("fetch", f);
    await api.post("/api/v1/x", okZ, {});
    const postHeaders = new Headers((f.mock.calls[0]?.[1] as RequestInit | undefined)?.headers as HeadersInit);
    const key = postHeaders.get("Idempotency-Key");
    expect(key).toBeTruthy();

    await api.get("/api/v1/x", okZ);
    const getHeaders = new Headers((f.mock.calls[1]?.[1] as RequestInit | undefined)?.headers as HeadersInit);
    expect(getHeaders.get("Idempotency-Key")).toBeNull();
  });
});
