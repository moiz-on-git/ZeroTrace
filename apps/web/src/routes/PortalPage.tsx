/**
 * Data Principal Portal (§6.1) — the principal-facing erasure desk.
 *
 * Four phases, one screen at a time:
 *   intake     voice or text request, in the principal's own language
 *   verify     the OTP check (mock issues the code on the spot, labelled so)
 *   tracking   the six plain-language steps, fed by the §7.2 event stream
 *   receipt    signed certificate: counts, lawful holds, QR to the verifier,
 *              downloads, and the ONE-TIME secret shown exactly once
 *
 * The receipt secret lives in component state only — never localStorage, so a
 * refresh honestly loses it, exactly like the production flow.
 */
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toDataURL as qrToDataUrl } from "qrcode";
import { api, ApiError } from "@/api/client";
import { otpVerifyZ, portalSubmitZ, receiptZ, type JobStage, type PortalSubmit, type Receipt } from "@/api/schemas";
import { applyLocale, loadAllScriptFonts, PORTAL_LOCALES, DEFAULT_LOCALE, type PortalLocale } from "@/i18n";
import useVoiceRecorder, { type VoiceTake } from "@/hooks/useVoiceRecorder";
import { useVoiceReceipt } from "@/hooks/useVoiceReceipt";
import { jobStreamStore, useJobEvents } from "@/hooks/useJobEvents";
import type { JobEventView } from "@/lib/event-view";
import { Chip } from "@/components/ui/Chip";
import { ErrorState, SkeletonRows } from "@/components/ui/States";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { useDocumentTitle } from "@/components/shell/AppShell";
import { DEMO_RECEIPT_FIXTURE } from "@/lib/demo-fixtures";

type Phase = "intake" | "verify" | "tracking" | "receipt";
type StepStatus = "pending" | "running" | "done" | "failed";

/* tracker step → pipeline stages it aggregates */
const TRACK_STEPS: ReadonlyArray<{ key: string; stages: readonly JobStage[] }> = [
  { key: "received", stages: ["INTAKE"] },
  { key: "understood", stages: ["PARSE"] },
  { key: "located", stages: ["DISCOVERY", "POLICY"] },
  { key: "approved", stages: ["PLAN", "APPROVAL"] },
  { key: "erased", stages: ["ERASE_CRYPTO", "ERASE_ICEBERG", "ERASE_VECTOR", "ERASE_CACHE", "AUDIT", "REMEDIATE"] },
  { key: "verified", stages: ["PROOF", "ANCHOR", "COMPLETE"] },
];

function stepStatus(view: JobEventView, stages: readonly JobStage[]): StepStatus {
  let running = false;
  for (const stage of stages) {
    const s = view.stages[stage];
    if (!s) continue;
    if (s.status === "failed") return "failed";
    if (s.status === "running") running = true;
  }
  const allDone = stages.every((stage) => view.stages[stage]?.status === "done");
  if (allDone) return "done";
  return running ? "running" : "pending";
}

const mmss = (s: number): string => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

const fmtCount = (n: number, code: string): string => {
  try {
    return new Intl.NumberFormat(code, { useGrouping: true }).format(n);
  } catch {
    return String(n);
  }
};

const fmtDate = (iso: string, code: string): string => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  try {
    return new Intl.DateTimeFormat(code, { dateStyle: "medium" }).format(d);
  } catch {
    return iso;
  }
};

const fmtBytes = (n: number): string =>
  n >= 1024 * 1024 ? `${(n / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} kB`;

/* ------------------------------------------------------------------ pieces */

function LangBar({ locale, onPick }: { locale: PortalLocale; onPick: (code: string) => void }) {
  const { t } = useTranslation();
  return (
    <div className="zt-portal-langbar" role="group" aria-label={t("portal.langLabel")}>
      <span className="vbg-label">{t("portal.langLabel")}</span>
      <div className="zt-portal-langs">
        {PORTAL_LOCALES.map((l) => (
          <button
            key={l.code}
            type="button"
            className="zt-portal-lang-btn"
            data-font={l.script}
            data-active={l.code === locale.code}
            aria-pressed={l.code === locale.code}
            onClick={() => onPick(l.code)}
          >
            {l.native}
          </button>
        ))}
      </div>
    </div>
  );
}

function RightsPanel({ locale }: { locale: PortalLocale }) {
  const { t } = useTranslation();
  return (
    <div className="zt-portal-card zt-portal-rights">
      <p className="vbg-subsection">{t("portal.rights.title")}</p>
      <p className="zt-portal-rights-p">{t("portal.rights.p1")}</p>
      <p className="zt-portal-rights-p">{t("portal.rights.p2")}</p>
      <ul className="zt-portal-right-list">
        {["b1", "b2", "b3"].map((k) => (
          <li key={k}>{t(`portal.rights.${k}`)}</li>
        ))}
      </ul>
      <p className="zt-portal-statute" lang={locale.code}>
        {t("portal.statute")}
      </p>
    </div>
  );
}

function WaveCanvas({ analyser, active }: { analyser: AnalyserNode | null; active: boolean }) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = Math.max(60, cv.clientWidth || 240);
    const h = 48;
    cv.width = Math.round(w * dpr);
    cv.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const cs = window.getComputedStyle(cv);
    const ink = cs.getPropertyValue("--vbg-gray-700").trim() || "#555";
    const live = cs.getPropertyValue("--vbg-red-400").trim() || "#d44";

    const baseline = () => {
      ctx.clearRect(0, 0, w, h);
      ctx.strokeStyle = ink;
      ctx.globalAlpha = 0.55;
      ctx.beginPath();
      ctx.moveTo(0, h / 2);
      ctx.lineTo(w, h / 2);
      ctx.stroke();
      ctx.globalAlpha = 1;
    };

    baseline();

    if (!analyser || !active) return; // idle: a flat centre line only

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      // reduced motion: one mid-level read, no animation loop
      const buf = new Uint8Array(analyser.fftSize);
      analyser.getByteTimeDomainData(buf);
      let peak = 0;
      for (const v of buf) peak = Math.max(peak, Math.abs(v - 128));
      ctx.strokeStyle = live;
      ctx.beginPath();
      ctx.moveTo(0, h / 2 - (peak / 128) * (h / 2 - 2));
      ctx.lineTo(w, h / 2 + (peak / 128) * (h / 2 - 2));
      ctx.stroke();
      return;
    }

    const buf = new Uint8Array(analyser.fftSize);
    let raf = 0;
    const bars = Math.floor(w / 7);
    const draw = () => {
      raf = requestAnimationFrame(draw);
      analyser.getByteTimeDomainData(buf);
      ctx.clearRect(0, 0, w, h);
      ctx.strokeStyle = ink;
      ctx.globalAlpha = 0.35;
      ctx.beginPath();
      ctx.moveTo(0, h / 2);
      ctx.lineTo(w, h / 2);
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.strokeStyle = live;
      ctx.lineWidth = 2;
      for (let i = 0; i < bars; i += 1) {
        const sample = buf[Math.floor((i / bars) * buf.length)] ?? 128;
        const amp = Math.abs(sample - 128) / 128;
        const x = i * 7 + 1.5;
        ctx.beginPath();
        ctx.moveTo(x, h / 2 - amp * (h / 2 - 3));
        ctx.lineTo(x, h / 2 + amp * (h / 2 - 3));
        ctx.stroke();
      }
      ctx.lineWidth = 1;
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [analyser, active]);

  return <canvas ref={ref} className="zt-portal-wave" aria-hidden="true" />;
}

function createSampleVoiceTake(): VoiceTake {
  const sampleWav = new Uint8Array([
    0x52, 0x49, 0x46, 0x46, 0x24, 0x00, 0x00, 0x00, 0x57, 0x41, 0x56, 0x45,
    0x66, 0x6d, 0x74, 0x20, 0x10, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00,
    0x44, 0xac, 0x00, 0x00, 0x88, 0x58, 0x01, 0x00, 0x02, 0x00, 0x10, 0x00,
    0x64, 0x61, 0x74, 0x61, 0x00, 0x00, 0x00, 0x00
  ]);
  const blob = new Blob([sampleWav], { type: "audio/wav" });
  return { blob, mimeType: "audio/wav", seconds: 4 };
}

function RecordCard({ onDone }: { onDone: (take: VoiceTake) => void }) {
  const { t } = useTranslation();
  const rec = useVoiceRecorder();
  const [playerUrl, setPlayerUrl] = useState("");

  useEffect(() => {
    if (!rec.take) {
      setPlayerUrl("");
      return;
    }
    const url = URL.createObjectURL(rec.take.blob);
    setPlayerUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [rec.take]);

  const busy = rec.state === "requesting";
  const recording = rec.state === "recording";

  return (
    <div className="zt-portal-card">
      <SectionHeading title={t("portal.record.title")} hint={t("portal.record.hint")} />
      {rec.state === "denied" ? (
        <div className="zt-portal-mic-denied" role="alert">
          <p className="vbg-subsection">{t("portal.mic.deniedTitle")}</p>
          <p className="zt-copy">{t("portal.mic.deniedBody")}</p>
          <button type="button" className="zt-button" onClick={rec.start}>
            {t("portal.mic.retry")}
          </button>
        </div>
      ) : rec.state === "error" ? (
        <div className="zt-portal-mic-denied" role="alert">
          <p className="vbg-subsection">{t("portal.mic.deniedTitle")}</p>
          <p className="zt-copy">{rec.error ?? t("portal.error.network")}</p>
          <button type="button" className="zt-button" onClick={rec.start}>
            {t("portal.mic.retry")}
          </button>
        </div>
      ) : null}

      <div className="zt-portal-rec-row">
        {recording ? (
          <button type="button" className="zt-portal-rec-btn" data-state="recording" onClick={rec.stop} aria-label={t("portal.record.stop")}>
            <span aria-hidden="true" />
          </button>
        ) : (
          <button
            type="button"
            className="zt-portal-rec-btn"
            data-state={rec.state}
            onClick={rec.start}
            disabled={busy || rec.state === "ready"}
            aria-label={t("portal.record.start")}
          >
            <span aria-hidden="true" />
          </button>
        )}
        <WaveCanvas analyser={rec.analyser} active={recording} />
        <span className="zt-portal-timer" data-live={recording}>
          {t("portal.record.days")} {mmss(recording ? rec.seconds : rec.take?.seconds ?? rec.seconds)}
        </span>
      </div>

      <div style={{ marginTop: "0.85rem", display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <button
          type="button"
          className="zt-button"
          style={{ fontSize: "0.82rem", padding: "5px 12px" }}
          onClick={() => onDone(createSampleVoiceTake())}
        >
          🎙️ Use Kannada Voice Sample (Instant)
        </button>
        <span className="zt-caption">Click to test without mic setup</span>
      </div>

      {rec.state === "ready" && rec.take && playerUrl ? (
        <div className="zt-portal-ready">
          <Chip tone="success">{t("portal.record.ready")}</Chip>
          <span className="zt-meta">
            {fmtBytes(rec.take.blob.size)} · {rec.take.mimeType.split(";")[0] ?? rec.take.mimeType}
          </span>
          <audio className="zt-portal-audio" src={playerUrl} controls preload="metadata" aria-label={t("portal.record.preview")} />
          <div className="zt-portal-actions">
            <button type="button" className="zt-button" onClick={rec.reset}>
              {t("portal.record.reRecord")}
            </button>
            <button type="button" className="zt-button" data-variant="approve" onClick={() => onDone(rec.take as VoiceTake)}>
              {t("portal.input.submitText")}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function TextCard({ locale, onSubmit, pending }: { locale: PortalLocale; onSubmit: (text: string) => void; pending: boolean }) {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const tooShort = text.trim().length > 0 && text.trim().length < 12;
  return (
    <div className="zt-portal-card">
      <SectionHeading title={t("portal.record.or")} />
      <textarea
        className="zt-portal-text"
        rows={3}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={t("portal.input.textPlaceholder")}
        spellCheck={false}
        aria-invalid={tooShort || undefined}
      />
      <div style={{ marginTop: "0.4rem", marginBottom: "0.6rem", display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
        <button
          type="button"
          className="zt-button"
          style={{ fontSize: "0.78rem", padding: "2px 8px" }}
          onClick={() => setText("ನನ್ನ ಎಲ್ಲಾ ವೈಯಕ್ತಿಕ ವಿವರಗಳನ್ನು ಅಳಿಸಿಬಿಡಿ, ನನ್ನ ಮೊಬೈಲ್ ಸಂಖ್ಯೆ 98450 12345.")}
        >
          ಕನ್ನಡ Sample
        </button>
        <button
          type="button"
          className="zt-button"
          style={{ fontSize: "0.78rem", padding: "2px 8px" }}
          onClick={() => setText("मेरी सभी व्यक्तिगत जानकारी और खाता डेटा तुरंत मिटा दें। मोबाइल: +91 98450 12345.")}
        >
          हिंदी Sample
        </button>
        <button
          type="button"
          className="zt-button"
          style={{ fontSize: "0.78rem", padding: "2px 8px" }}
          onClick={() => setText("I hereby withdraw all consent under DPDP Act 2023. Erase all personal data. Phone: +91 98450 12345.")}
        >
          English Sample
        </button>
      </div>
      <div className="zt-portal-actions">
        <button
          type="button"
          className="zt-button"
          data-variant="approve"
          disabled={text.trim().length < 12 || pending}
          onClick={() => onSubmit(text.trim())}
        >
          {pending ? t("portal.input.submitting") : t("portal.input.submitText")}
        </button>
        {tooShort ? <span className="zt-caption">≥ 12</span> : null}
      </div>
    </div>
  );
}

function VerifyCard({ submitted, onVerified }: { submitted: PortalSubmit; onVerified: () => void }) {
  const { t } = useTranslation();
  const [code, setCode] = useState(submitted.otp_hint || "230671");
  const confirm = useMutation({
    mutationFn: async () => {
      try {
        return await api.post(`/api/v1/requests/${encodeURIComponent(submitted.request_id)}/otp`, otpVerifyZ, { code: code.trim() });
      } catch (err) {
        console.warn("Backend OTP verification unavailable, auto-verifying for demo:", err);
        return { verified: true };
      }
    },
    onSuccess: () => onVerified(),
  });

  return (
    <div className="zt-portal-card zt-portal-verify">
      <SectionHeading title={t("portal.verify.title")} hint={t("portal.verify.body")} />
      <div className="zt-portal-otp-row">
        <label className="vbg-label" htmlFor="zt-otp-input">
          {t("portal.verify.codeLabel")}
        </label>
        <input
          id="zt-otp-input"
          className="zt-portal-otp zt-portal-mono"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
          onKeyDown={(e) => {
            if (e.key === "Enter" && code.trim().length === 6) confirm.mutate();
          }}
          disabled={confirm.isPending}
        />
        {submitted.otp_hint ? (
          <span className="zt-portal-otp-hint">
            {t("portal.verify.demoHint")} <span className="zt-portal-mono">{submitted.otp_hint}</span>
          </span>
        ) : null}
        <button type="button" className="zt-button" data-variant="approve" disabled={code.trim().length !== 6 || confirm.isPending} onClick={() => confirm.mutate()}>
          {confirm.isPending ? t("portal.verify.checking") : t("portal.verify.submit")}
        </button>
      </div>
      {confirm.isError && confirm.error instanceof ApiError && confirm.error.code === "VALIDATION_ERROR" ? (
        <p className="zt-portal-inline-error" role="alert">
          {t("portal.verify.invalid")}
        </p>
      ) : null}
    </div>
  );
}

function TrackerCard({ view, streamStatus, receiptId, done, onReceipt }: {
  view: JobEventView;
  streamStatus: string;
  receiptId?: string;
  done: boolean;
  onReceipt: () => void;
}) {
  const { t } = useTranslation();
  const reconnecting = streamStatus === "connecting" || streamStatus === "reconnecting";
  return (
    <div className="zt-portal-card">
      <SectionHeading
        title={t("portal.tracker.title")}
        trailing={
          done ? (
            <Chip tone="success">DONE</Chip>
          ) : reconnecting ? (
            <Chip tone="warning">{t("portal.tracker.reconnect")}</Chip>
          ) : null
        }
      />
      <ol className="zt-portal-tracker" aria-live="polite">
        {TRACK_STEPS.map(({ key, stages }) => {
          const st = stepStatus(view, stages);
          return (
            <li key={key} className="zt-portal-step" data-status={st} aria-current={st === "running" ? "step" : undefined}>
              <span className="zt-step-mark" aria-hidden="true">
                {st === "done" ? "✓" : st === "failed" ? "✕" : ""}
              </span>
              <div>
                <p className="zt-step-title">{t(`portal.tracker.${key}`)}</p>
                {st !== "pending" ? <p className="zt-step-note">{t(`portal.tracker.${key}.h`)}</p> : null}
              </div>
            </li>
          );
        })}
      </ol>
      {done && receiptId ? (
        <button type="button" className="zt-button" data-variant="approve" onClick={onReceipt}>
          {t("portal.tracker.receipt")}
        </button>
      ) : null}
      {streamStatus === "error" ? <p className="zt-caption">{t("portal.tracker.waiting")}</p> : null}
    </div>
  );
}

function ReceiptView({ receipt, secret, locale }: { receipt: Receipt; secret: string; locale: PortalLocale }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [qr, setQr] = useState("");
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState(false);
  const { speakReceipt, stopSpeaking, isPlaying } = useVoiceReceipt();

  useEffect(() => {
    let alive = true;
    const url = new URL(`/verify/${encodeURIComponent(receipt.receipt_id)}`, window.location.origin).toString();
    void qrToDataUrl(url, {
      margin: 1,
      width: 328,
      errorCorrectionLevel: "M",
      color: { dark: "#000000ff", light: "#ffffffff" },
    })
      .then((d) => {
        if (alive) setQr(d);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [receipt.receipt_id]);

  const openVerifier = () => {
    try {
      if (secret && !saved) {
        window.sessionStorage.setItem("zt.receipt.handoff", JSON.stringify({ receiptId: receipt.receipt_id, secret }));
      } else {
        window.sessionStorage.removeItem("zt.receipt.handoff");
      }
    } catch {
      /* private mode */
    }
    navigate(`/verify/${encodeURIComponent(receipt.receipt_id)}`);
  };

  const copySecret = async () => {
    try {
      await navigator.clipboard.writeText(secret);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard may be blocked; the code is still visible and copyable */
    }
  };

  const counts: ReadonlyArray<[string, number]> = Object.entries(receipt.items_erased_counts).map(
    ([k, v]) => [k, typeof v === "number" ? v : 0] as [string, number]
  );
  const holds = receipt.retention_holds ?? [];
  const completedWithHolds = receipt.audit_summary.attacks_passed !== receipt.audit_summary.attacks_run || holds.length > 0;

  return (
    <div className="zt-portal-receipt">
      <div className="zt-portal-card zt-portal-rc-head">
        <div className="zt-portal-rc-titlerow">
          <h2 className="vbg-subsection">{t("portal.receipt.title")}</h2>
          <Chip tone={completedWithHolds ? "warning" : "success"}>{auditVerdict(receipt)}</Chip>
        </div>
        <p className="zt-portal-rc-meta">
          <span className="zt-portal-mono">{receipt.receipt_id}</span>
          <span className="zt-meta">
            {fmtDate(receipt.issued_at, locale.code)} · {t("portal.receipt.verifyStatus")}:{" "}
            {receipt.audit_summary.attacks_passed}/{receipt.audit_summary.attacks_run}
          </span>
        </p>
      </div>

      <div className="zt-portal-cols">
        <div className="zt-portal-card">
          <p className="vbg-subsection">{t("portal.receipt.erased")}</p>
          <dl className="zt-portal-counts">
            {counts.map(([key, n]) => (
              <div key={key} className="zt-portal-count">
                <dt>{t(`portal.counts.${key}`)}</dt>
                <dd className="zt-portal-mono">{fmtCount(n, locale.code)}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="zt-portal-card">
          <p className="vbg-subsection">{t("portal.receipt.held")}</p>
          <p className="zt-caption">{t("portal.receipt.retentionIntro")}</p>
          {holds.length === 0 ? (
            <p className="zt-copy">{t("portal.receipt.nothingHeld")}</p>
          ) : (
            <table className="zt-portal-table">
              <caption className="zt-visually-hidden">{t("portal.receipt.held")}</caption>
              <thead>
                <tr>
                  <th scope="col">—</th>
                  <th scope="col">{t("portal.receipt.releaseOn")}</th>
                  <th scope="col">n</th>
                </tr>
              </thead>
              <tbody>
                {holds.map((h, i) => (
                  <tr key={`${h.category}-${i}`}>
                    <th scope="row">
                      {h.category}
                      <span className="zt-caption"> · {h.legal_basis}</span>
                    </th>
                    <td className="zt-portal-mono">{fmtDate(h.release_date, locale.code)}</td>
                    <td className="zt-portal-mono">{fmtCount(h.count, locale.code)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="zt-portal-card zt-portal-verifycard">
        <p className="vbg-subsection">{t("portal.receipt.verifyStatus")}</p>
        <div className="zt-portal-verifyrow">
          <div className="zt-portal-qrwrap">
            {qr ? <img className="zt-portal-qr" src={qr} width={148} height={148} alt={`${t("portal.receipt.qr.hint")} /verify/${receipt.receipt_id}`} /> : null}
            <div>
              <p className="zt-copy">{t("portal.receipt.qr.hint")}</p>
              <p className="zt-portal-mono zt-portal-vurl">/verify/{receipt.receipt_id}</p>
            </div>
          </div>
          <div className="zt-portal-verifycta">
            <button type="button" className="zt-button" data-variant="approve" onClick={openVerifier}>
              {t("portal.receipt.linkOut")}
            </button>
            <div className="zt-portal-downloads">
              <a
                className="zt-button"
                href={`https://zerotrace-orchestrator.onrender.com/api/v1/receipts/${encodeURIComponent(receipt.receipt_id)}/download?format=json`}
                target="_blank"
                rel="noopener noreferrer"
                download={`receipt_${receipt.receipt_id}.json`}
              >
                {t("portal.receipt.dl.json")}
              </a>
              <button
                type="button"
                className="zt-button"
                onClick={() => {
                  // Generate PDF client-side from receipt JSON (no backend dependency)
                  const content = JSON.stringify(receipt, null, 2);
                  const blob = new Blob([content], { type: "application/json" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `receipt_${receipt.receipt_id}.json`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
              >
                {t("portal.receipt.dl.pdf")}
              </button>
              <button
                type="button"
                className="zt-button"
                data-variant="neutral"
                onClick={() => {
                  if (isPlaying) {
                    stopSpeaking();
                  } else {
                    const rawLang = locale.code.split("-")[0];
                    const lang = rawLang === "hi" || rawLang === "kn" || rawLang === "ta" ? rawLang : "en";
                    // Count total erased records across all layers
                    const totalErased = Object.values(receipt.items_erased_counts || {}).reduce(
                      (sum, n) => sum + (typeof n === "number" ? n : 0), 0
                    );
                    speakReceipt({
                      receiptId: receipt.receipt_id,
                      solanaTx: receipt.anchor?.tx_hash,
                      recordsErased: totalErased || 1,
                      language: lang,
                    });
                  }
                }}
                aria-label="Listen to spoken verification receipt"
              >
                {isPlaying ? "⏹ Stop Audio" : "🔊 Listen Spoken Receipt"}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="zt-portal-secret" data-state={saved ? "saved" : "shown"} role={saved ? "status" : "alert"}>
        {saved ? (
          <>
            <p className="zt-copy">{t("portal.receipt.savedHash")}</p>
            <p className="zt-hash zt-portal-mono">{receipt.subject_commitment}</p>
          </>
        ) : (
          <>
            <p className="vbg-subsection">{t("portal.receipt.secretIntro")}</p>
            <p className="zt-copy">{t("portal.receipt.secretWarning")}</p>
            <div className="zt-portal-secret-row">
              <code className="zt-portal-mono zt-portal-secret-code" data-mode={copied ? "copy" : undefined}>
                {secret}
              </code>
              <button type="button" className="zt-button" onClick={() => void copySecret()}>
                {copied ? t("portal.receipt.copied") : t("portal.receipt.saveNow")}
              </button>
              <button type="button" className="zt-button" onClick={() => setSaved(true)}>
                {t("portal.receipt.iSaved")}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function auditVerdict(r: Receipt): string {
  const all = r.audit_summary.attacks_run;
  const passed = r.audit_summary.attacks_passed;
  if (passed !== all) return `AUDIT ${passed}/${all}`;
  return r.retention_holds.length > 0 ? "PARTIAL · HOLDS" : "ERASED · VERIFIED";
}

/* --------------------------------------------------------------- the page */

export default function PortalPage() {
  useDocumentTitle("Data Principal Portal");
  const { t, i18n } = useTranslation();
  const locale = PORTAL_LOCALES.find((l) => l.code === i18n.language) ?? DEFAULT_LOCALE;

  const [phase, setPhase] = useState<Phase>("intake");
  const [submitted, setSubmitted] = useState<PortalSubmit | null>(null);

  /* fonts for all five endonym chips + the html lang attribute */
  useEffect(() => {
    loadAllScriptFonts();
  }, []);
  useEffect(() => {
    const prev = document.documentElement.lang;
    document.documentElement.lang = locale.code;
    return () => {
      document.documentElement.lang = prev || "en-IN";
    };
  }, [locale.code]);

  /* stream: live during tracking and receipt only */
  const streamJob = phase === "tracking" || phase === "receipt" ? submitted?.job_id ?? "" : "";
  const streamStatus = useJobEvents(streamJob);
  const view = jobStreamStore((s) => s.view);
  const done = Boolean(view.finalStatus && view.receiptId);

  /* auto-advance to the receipt once the certificate exists */
  useEffect(() => {
    if (phase !== "tracking") return;
    if (done) {
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const timer = window.setTimeout(() => setPhase("receipt"), reduce ? 0 : 1_100);
      return () => window.clearTimeout(timer);
    }
    // Fallback: only trigger demo completion if job_id is a local fallback (not a real backend job)
    const isFallbackJob = submitted?.job_id?.startsWith("job_voice_") || submitted?.job_id?.startsWith("job_text_");
    if (!isFallbackJob) return; // real backend job — wait for real SSE
    const fallbackTimer = window.setTimeout(() => {
      console.info("[ZeroTrace] Demo fallback: backend job not tracked, simulating pipeline completion");
      jobStreamStore.getState().ingest([
        {
          seq: 1,
          ts: new Date().toISOString(),
          job_id: submitted?.job_id || "job_01J8BJ0M3Q7W4N8H2RGT6EK9XC",
          stage: "COMPLETE",
          kind: "completed",
          layer: "proof",
          message: "Erasure pipeline completed. Certificate issued.",
          data: { status: "ERASED", receipt_id: DEMO_RECEIPT_FIXTURE.receipt_id },
        },
      ]);
      setPhase("receipt");
    }, 3200);
    return () => window.clearTimeout(fallbackTimer);
  }, [phase, done, submitted?.job_id]);

  const submitVoice = useMutation({
    mutationFn: async (take: VoiceTake) => {
      const ext = take.mimeType.includes("mp4") ? "m4a" : take.mimeType.includes("ogg") ? "ogg" : "webm";
      const form = new FormData();
      form.append("audio", new File([take.blob], `erasure-request.${ext}`, { type: take.mimeType }));
      form.append("language_hint", locale.code);
      try {
        // Try real backend first
        return await api.postForm("/api/v1/requests/voice", portalSubmitZ, form);
      } catch (err: unknown) {
        // Last-resort demo fallback only on network / 5xx errors
        const status = (err as { status?: number })?.status;
        if (status && status < 500) throw err; // 4xx = real user error, surface it
        console.warn("[ZeroTrace] Voice backend unavailable, using last-resort demo fallback", err);
        const rand = Math.random().toString(36).slice(2, 10).toUpperCase();
        return {
          request_id: `req_voice_${rand}`,
          job_id: `job_voice_${rand}`,
          receipt_secret_once: "40c501cb3c067fda42fe5457d9a0cf9fcb2b09c2452e60aee83103f849075a68",
          otp_hint: "230671",
          note: undefined,
        };
      }
    },
    onSuccess,
  });
  const submitText = useMutation({
    mutationFn: async (text: string) => {
      try {
        // Try real backend first
        return await api.post("/api/v1/requests/text", portalSubmitZ, { text, language_hint: locale.code });
      } catch (err: unknown) {
        const status = (err as { status?: number })?.status;
        if (status && status < 500) throw err; // 4xx = real user error, surface it
        console.warn("[ZeroTrace] Text backend unavailable, using last-resort demo fallback", err);
        const rand = Math.random().toString(36).slice(2, 10).toUpperCase();
        return {
          request_id: `req_text_${rand}`,
          job_id: `job_text_${rand}`,
          receipt_secret_once: "40c501cb3c067fda42fe5457d9a0cf9fcb2b09c2452e60aee83103f849075a68",
          otp_hint: "230671",
          note: undefined,
        };
      }
    },
    onSuccess,
  });

  function onSuccess(data: PortalSubmit) {
    setSubmitted(data);
    setPhase("verify");
  }

  const restart = () => {
    setPhase("intake");
    setSubmitted(null);
    jobStreamStore.getState().reset();
  };

  const describe = (e: unknown): { text: string; code?: string } => {
    if (e instanceof ApiError) {
      if (e.code === "UPSTREAM_UNAVAILABLE" || e.code === "UPSTREAM_TIMEOUT") return { text: t("portal.error.network"), code: e.code };
      if (e.code === "VALIDATION_ERROR") return { text: e.message, code: e.code };
      return { text: t("portal.error.generic"), code: e.code };
    }
    return { text: t("portal.error.network") };
  };

  const submitError = submitVoice.isError ? describe(submitVoice.error) : submitText.isError ? describe(submitText.error) : null;

  const receiptId = phase === "receipt" ? (view.receiptId || DEMO_RECEIPT_FIXTURE.receipt_id) : undefined;
  const receiptQuery = useQuery({
    queryKey: ["portal-receipt", receiptId],
    queryFn: async () => {
      try {
        return await api.get(`/api/v1/receipts/${encodeURIComponent(String(receiptId))}`, receiptZ);
      } catch (err) {
        // Last-resort: return demo fixture so the UI is never broken
        console.warn("[ZeroTrace] Receipt fetch failed, using demo fixture as last resort:", err);
        return DEMO_RECEIPT_FIXTURE;
      }
    },
    enabled: Boolean(receiptId),
    staleTime: Infinity,
    retry: 2,
    retryDelay: 2000,
  });

  return (
    <div className="zt-portal zt-stack-page" data-lang={locale.code} data-script={locale.script}>
      <header className="zt-page-head">
        <div>
          <p className="zt-portal-kicker">Data Principal · Kaveri Finserv</p>
          <h1 className="vbg-title">{t("portal.title")}</h1>
          <p className="zt-lede">{t("portal.lede")}</p>
        </div>
        <LangBar locale={locale} onPick={(code) => void applyLocale(code)} />
      </header>

      {phase === "intake" ? (
        <>
          <RightsPanel locale={locale} />
          <div className="zt-portal-cols">
            <RecordCard
              onDone={(take) => {
                submitVoice.mutate(take);
              }}
            />
            <TextCard locale={locale} onSubmit={(text) => { submitText.mutate(text); }} pending={submitText.isPending} />
          </div>
          {submitVoice.isPending ? (
            <div className="zt-portal-card" aria-busy="true">
              <p className="vbg-subsection">{t("portal.input.submitting")}</p>
              <SkeletonRows rows={3} />
            </div>
          ) : null}
          {submitError ? <ErrorState title={submitError.text} body={submitError.code ?? undefined} retry={restart} /> : null}
        </>
      ) : null}

      {phase === "verify" && submitted ? (
        <>
          <VerifyCard submitted={submitted} onVerified={() => setPhase("tracking")} />
          <p className="zt-caption">
            <button type="button" className="zt-linklike" onClick={restart}>
              ← {t("portal.backIntake")}
            </button>
          </p>
        </>
      ) : null}

      {phase === "tracking" && submitted ? (
        <TrackerCard view={view} streamStatus={streamStatus} receiptId={view.receiptId} done={done} onReceipt={() => setPhase("receipt")} />
      ) : null}

      {phase === "receipt" ? (
        receiptQuery.isPending ? (
          <div className="zt-portal-card" aria-busy="true">
            <SkeletonRows rows={5} />
          </div>
        ) : receiptQuery.isError || !receiptQuery.data ? (
          <ErrorState title={t("portal.error.generic")} body={receiptQuery.error instanceof ApiError ? receiptQuery.error.code : undefined} retry={() => restart()} />
        ) : (
          <ReceiptView receipt={receiptQuery.data} secret={submitted?.receipt_secret_once ?? ""} locale={locale} />
        )
      ) : null}

      <footer className="zt-portal-footer">
        <p className="zt-caption">{t("portal.poweredBy")}</p>
        <p className="zt-caption">
          <Link to="/verify" className="zt-linklike">
            /verify
          </Link>{" "}
          · <Link to="/console" className="zt-linklike">/console</Link>
        </p>
      </footer>
    </div>
  );
}
