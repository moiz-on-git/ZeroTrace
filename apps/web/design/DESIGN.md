# ZeroTrace Web — Design System

The web app's look is **Vercel/Geist engineering-metro**, applied on top of a byte-identical copy of
the user-supplied foundation (`assets/vercel-brand.css` → `src/styles/vercel-brand.css`). That file is
the design authority: it owns tokens, primitives and auto light/dark. Everything app-owned lives in
`src/styles/app.css` under the `zt-*` namespace and **may only read public `--vbg-*` token families**.

## Layering rules

| Layer | File | Namespace | May do |
| --- | --- | --- | --- |
| Foundation (do not edit) | `vercel-brand.css` | `vbg-*`, `--vbg-*` mounted on `:where(.vbg-report)` | everything |
| Fonts | `fonts.css` | `@font-face` "Geist" / "Geist Mono" (self-hosted woff2) | register faces only |
| App | `app.css` | `zt-*` | read documented `--vbg-*` families, never redeclare/alias tokens, never restyle `vbg-*` primitives |

The app root mounts `<div class="vbg-report">` (AppShell), which scopes the tokens and enables
`light-dark()` + `color-scheme` so **light/dark comes for free and always renders readable**.

## Typography

* **Sans:** Geist (self-hosted variable woff2, latin + latin-ext). Family registered exactly as
  `"Geist"` because the foundation binds those names.
* **Mono:** Geist Mono — every hash, id, ULID, tx hash, root, seq number, metric counter.
* Text roles come from foundation types: display → title → heading-16/14 → body → compact →
  metadata/caption. We never set ad-hoc font sizes.

## Numbers & hashes

* All counters and amounts use the `.zt-num` class → **monospace + tabular numerals**: durations,
  ₹ costs, byte counts, file counts, block heights. No proportional-font digits anywhere data is read.
* Ids/hashes render via `.zt-hash`/`.zt-id` — `overflow-wrap: anywhere`, never truncated by CSS
  ellipsis unless first16+last8 is shown with the full value on `title`.
* Currency is Indian format (`en-IN`): ₹3.5 lakh payouts, ₹10 per certificate — matching pricing copy.

## Colour = meaning only

State colours are reserved. Pattern: **tone chip/dot + plain text cue** (never colour alone).

| Token family | Used for |
| --- | --- |
| `--vbg-color-success` | PASS verdicts, anchors confirmed, checksum match, done stages |
| `--vbg-color-error` | FOUND (ghost), FAIL, purged, checksum mismatch, danger buttons, destructive decisions |
| `--vbg-color-warning` | targeted files, lawful holds, awaiting approval, reconnecting |
| `--vbg-color-info` | running stages, live streams, neutral explanations |

No gradients, no glass, no shadows-as-decoration. Depth = 1px borders and surface steps only.

## Space & radius

Foundation space steps (`--vbg-space-1..10`) only. Page rhythm: rail 232px (collapses < 900px),
page columns at ≥1100px (main + 320px sticky job rail), section gap 9, inner gaps 2–6, radius small
for containers/inputs, medium for panels. Scroll-margin on every section anchor (84px) because of the
sticky top bar.

## Screens (as built at M3)

1. **Overview/** — editorial landing: what ZeroTrace is, the three traps, one-call integration
   snippet, pricing. No hero art.
2. **DPO console queue `/console`** — dense semantic table, not cards. Row = status chip, job id
   (mono), subject (masked), file counts, updated-time. Filter input + status chips. Empty state
   explains where jobs come from.
3. **Job detail `/console/jobs/:id`** — the M3 centerpiece:
   * sticky rail: at-a-glance Kvs + section nav;
   * stage timeline band (15 §7.2 stages, duration in mono);
   * Intent: transcript quote, key-value facts, masked identifier chips (§ no-PII), statute list
     with cites, agent trace table;
   * Lineage: ReactFlow + dagre graph, nodes appear as DISCOVERY reports them, `erase`/`hold`
     decisions colour-coded, controls + dotted background only;
   * Plan & blast radius: 460-cell SVG heat grid (one square per file; targeted amber, rewritten
     green, purged brick), cost comparison bars, warnings, holds table, **hold-to-confirm approval**
     (1.2 s press-and-hold with rAF fill; keyboard spacebar supported);
   * Execution: four lanes (crypto/iceberg/vector/cache) with live counters from §7.2 metrics;
   * Audit: round-by-round attack table + verdict chips + collateral footer + ghost note;
   * Proof: pre/post/diff roots (mono), leaf counts, receipt signature, anchor box (submitted →
     confirmed → explorer link), evidence downloads;
   * Event log: TanStack Virtual, 22 px rows, stage/kind columns, follow toggle + resume chip.
4. **Portal / Adversary / Verifier** — honest reserved screens naming exactly what lands next and
   the contract paths they will call. No fake features.
5. **Demo director `/demo`** — working preflight lights, scenario seeding (success/ghost/holds),
   reset. Destructive action asks twice on the real backend.
6. **404**, plain.

## Motion

* rAF-batched SSE ingest (no layout thrash during bursts);
* rAF hold-to-confirm fill (1.2 s);
* dagre layout recalculated per reveal, fit re-centres with a 140 ms duration; no spring/parallax.
* Reduced-motion honoured by the foundation.

## Component inventory (shared UI)

`Chip` (tone+label, semantic only) · `Dot` (icon cue) · `SectionHeading` (title + hint + trailing)
· `Kv/KvPair` (definition list) · `CostComparison` (measured bars, assumptions footnote) ·
`SkeletonRows`, `EmptyState`, `ErrorState` (retry carries the error code in the caption).

## Known deviations

* TanStack Table v9 dropped for the queue in favour of a hand-rolled semantic table (new renamed
  v9 API was high-risk under the hackathon clock); TanStack Query/Virtual/xyflow are used as
  specified. Revisit at M11.
* Radix primitives are installed and used sparingly (dialog/switch planned for M8/M9 meetings);
  no custom forks of them.
* i18next wired at M8; strings are currently plain English with real microcopy.
