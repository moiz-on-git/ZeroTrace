#!/usr/bin/env node
/**
 * ZeroTrace frontend mock server — replays generated fixtures as SSE with
 * realistic pacing, Last-Event-ID-style resume ("from" query or header) and
 * a compressed catch-up pace for resumed sessions. Used by Playwright e2e
 * and as a no-service-worker fallback; MSW covers interactive dev.
 *
 *   node mock-server/index.mjs [--port 3100] [--speed 1] [--scenario success]
 *
 * Endpoints:
 *   GET /jobs/:id/events          SSE (fixture events; ?from=,?speed=,?scenario=)
 *   GET /health                   liveness
 */
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const fixturesDir = resolve(here, "../src/mocks/fixtures");
const FIXTURES = {
  success: JSON.parse(readFileSync(join(fixturesDir, "success.json"), "utf8")),
  ghost: JSON.parse(readFileSync(join(fixturesDir, "ghost.json"), "utf8")),
  holds: JSON.parse(readFileSync(join(fixturesDir, "holds.json"), "utf8")),
};

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i > -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const PORT = Number(arg("--port", 3100));
const DEFAULT_SPEED = Math.max(Number(arg("--speed", 1)), 0.1);
const DEFAULT_SCENARIO = arg("--scenario", "success");

const base = new Date("2026-10-17T09:30:00.000Z").getTime();
const REL = (fx, i) => Date.parse(fx.events[i].ts) - base;

function replay(fx, from, speed, resumed, res) {
  const head = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
  };
  res.writeHead(200, head);

  let lastSent = -1;
  const pace = () => {
    if (res.destroyed) return;
    const ev = fx.events[toSendIndex];
    void ev;
  };
  const toSendIndex = fx.events.findIndex((e) => e.seq > from);
  void pace;

  const events = fx.events;
  let idx = 0;
  while (idx < events.length && events[idx].seq <= from) idx++;

  const write = (i) => {
    res.write(`data: ${JSON.stringify(events[i])}\n\n`);
    lastSent = i;
  };

  const end = () => {
    if (!res.destroyed && !res.writableEnded) res.end();
  };

  if (idx >= events.length) {
    write(events.length - 1);
    end();
    return;
  }

  writeNext(idx);

  function writeNext(i) {
    if (res.destroyed || res.writableEnded) return;
    if (i >= events.length) {
      end();
      return;
    }
    write(i);
    const nxt = i + 1;
    if (nxt >= events.length) {
      end();
      return;
    }
    let gap = REL(events, nxt) - REL(events, i);
    gap = Math.max(30, Math.min(resumed ? 240 : 5_000, (resumed ? gap / 6 : gap) / speed || 60));
    const h = setTimeout(() => writeNext(nxt), gap);
    res.on("close", () => clearTimeout(h));
  }
  void lastSent;
}

const server = createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  res.setHeader("Access-Control-Allow-Origin", "*");
  if (req.method === "OPTIONS") {
    res.writeHead(204).end();
    return;
  }

  if (url.pathname === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ ok: true, scenario: url.searchParams.get("scenario") ?? DEFAULT_SCENARIO }));
    return;
  }

  const m = url.pathname.match(/^\/jobs\/([^/]+)\/events$/);
  if (m && req.method === "GET") {
    const scenario = FIXTURES[url.searchParams.get("scenario")] ? url.searchParams.get("scenario") : DEFAULT_SCENARIO;
    const fx = FIXTURES[scenario];
    if (String(fx.job.id) !== decodeURIComponent(m[1])) {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ data: null, error: { code: "NOT_FOUND", message: "unknown job for this scenario" } }));
      return;
    }
    const from = Number(url.searchParams.get("from") ?? req.headers["last-event-id"] ?? 0) || 0;
    const speed = Number(url.searchParams.get("speed") ?? DEFAULT_SPEED) || DEFAULT_SPEED;
    replay(fx, from, speed, from > 0, res);
    return;
  }

  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ data: null, error: { code: "NOT_FOUND", message: "not mocked here" } }));
});

server.listen(PORT, () => {
  console.log(`mock-server listening on http://localhost:${PORT} (scenario: ${DEFAULT_SCENARIO}, speed: ${DEFAULT_SPEED})`);
});
