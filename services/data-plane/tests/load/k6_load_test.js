/**
 * ZeroTrace Data Plane — k6 Load Test
 * 
 * Tests:
 * 1. Health check throughput
 * 2. Inventory endpoint under load
 * 3. Subject lookup under load
 * 4. Burst traffic handling
 * 
 * Usage:
 *   k6 run tests/load/k6_load_test.js --env BASE_URL=http://localhost:8002 --env SERVICE_KEY=zt-dev-service-key-2026
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8002';
const SERVICE_KEY = __ENV.SERVICE_KEY || 'zt-dev-service-key-2026';

const headers = {
    'X-Service-Key': SERVICE_KEY,
    'Content-Type': 'application/json',
};

// ── Custom metrics ────────────────────────────────────────────────────────────
const errorRate = new Rate('errors');
const inventoryLatency = new Trend('inventory_latency_ms');
const healthLatency = new Trend('health_latency_ms');

// ── Test options ───────────────────────────────────────────────────────────────
export const options = {
    stages: [
        // Ramp up to 20 VUs over 30s
        { duration: '30s', target: 20 },
        // Hold at 20 VUs for 1 minute
        { duration: '1m', target: 20 },
        // Ramp up to 50 VUs over 30s (stress test)
        { duration: '30s', target: 50 },
        // Hold at 50 VUs for 1 minute
        { duration: '1m', target: 50 },
        // Ramp down to 0
        { duration: '30s', target: 0 },
    ],
    thresholds: {
        // 95% of requests should complete under 500ms
        http_req_duration: ['p(95)<500'],
        // Error rate should be under 5%
        errors: ['rate<0.05'],
        // 99% of health checks should be under 100ms
        health_latency_ms: ['p(99)<100'],
    },
    noConnectionRefuse: true,
};

// ── Test scenarios ─────────────────────────────────────────────────────────────

export default function () {
    // ── 1. Health check (fast, no auth) ──────────────────────────────────────
    group('Health Check', () => {
        const start = Date.now();
        const res = http.get(`${BASE_URL}/health`);
        healthLatency.add(Date.now() - start);

        check(res, {
            'health is 200': (r) => r.status === 200,
            'health says ok': (r) => r.json('status') === 'ok',
        }) || errorRate.add(1);
    });

    // ── 2. Liveness probe ────────────────────────────────────────────────────
    group('Liveness', () => {
        const res = http.get(`${BASE_URL}/live`);
        check(res, {
            'liveness is 200': (r) => r.status === 200,
            'liveness says alive': (r) => r.json('status') === 'alive',
        }) || errorRate.add(1);
    });

    // ── 3. Metrics endpoint ──────────────────────────────────────────────────
    group('Metrics', () => {
        const res = http.get(`${BASE_URL}/metrics`);
        check(res, {
            'metrics is 200': (r) => r.status === 200,
            'metrics has zt_ prefix': (r) => r.body.includes('zt_'),
        }) || errorRate.add(1);
    });

    // ── 4. Inventory (authenticated) ──────────────────────────────────────────
    group('Inventory', () => {
        const start = Date.now();
        const res = http.get(`${BASE_URL}/v1/inventory`, { headers });
        inventoryLatency.add(Date.now() - start);

        check(res, {
            'inventory is 200': (r) => r.status === 200,
            'inventory has tables': (r) => r.json('data.tables') !== null,
        }) || errorRate.add(1);
    });

    // ── 5. Subject lookup ───────────────────────────────────────────────────
    group('Locate', () => {
        const res = http.post(
            `${BASE_URL}/v1/locate`,
            JSON.stringify({
                identifiers: [
                    { type: 'phone', value: '9845012345' },
                    { type: 'email', value: 'ananya.krishnamurthy@example.in' },
                ],
            }),
            { headers }
        );
        check(res, {
            'locate is 200': (r) => r.status === 200,
        }) || errorRate.add(1);
    });

    // ── 6. Demo subjects ─────────────────────────────────────────────────────
    group('Demo Subjects', () => {
        const res = http.get(`${BASE_URL}/v1/demo/subjects`, { headers });
        check(res, {
            'subjects is 200': (r) => r.status === 200,
            'subjects has hero': (r) => {
                const subjects = r.json('data.subjects');
                return subjects && subjects.some(s => s.is_hero === true);
            },
        }) || errorRate.add(1);
    });

    sleep(0.1); // Small delay between iterations
}

// ── Teardown: print summary ─────────────────────────────────────────────────────
export function teardown(data) {
    console.log('\n=== Load Test Complete ===');
    console.log(`Base URL: ${BASE_URL}`);
    console.log('Check k6 summary for detailed metrics.');
}
