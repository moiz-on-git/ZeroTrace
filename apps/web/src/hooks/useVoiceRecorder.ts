/**
 * Microphone capture for the Data Principal Portal.
 *
 * - MediaRecorder with an explicit codec ladder (webm/opus → webm → mp4 →
 *   ogg), because Safari speaks only mp4 and Chrome only webm.
 * - An AnalyserNode is exposed for the waveform: the drawing itself stays in
 *   the component so the hook never touches the canvas.
 * - Permission denial is a first-class state (`denied`), not an error — the
 *   portal then offers the text channel, which carries the same legal weight.
 */
import { useCallback, useEffect, useRef, useState } from "react";

export type VoiceRecorderState = "idle" | "requesting" | "recording" | "ready" | "denied" | "error";

export interface VoiceTake {
  blob: Blob;
  mimeType: string;
  seconds: number;
}

export interface VoiceRecorderApi {
  state: VoiceRecorderState;
  seconds: number;
  take: VoiceTake | null;
  error: string | null;
  /** null whenever not recording — the canvas effect reacts to this. */
  analyser: AnalyserNode | null;
  start: () => void;
  stop: () => void;
  /** Discards the take and returns the button to "idle". */
  reset: () => void;
}

const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"] as const;

function pickMime(): string {
  if (typeof MediaRecorder === "undefined") return "";
  for (const m of MIME_CANDIDATES) {
    try {
      if (MediaRecorder.isTypeSupported(m)) return m;
    } catch {
      /* older Safari without isTypeSupported falls through */
    }
  }
  return "";
}

export function useVoiceRecorder(): VoiceRecorderApi {
  const [state, setState] = useState<VoiceRecorderState>("idle");
  const [seconds, setSeconds] = useState(0);
  const [take, setTake] = useState<VoiceTake | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);

  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const audioCtx = useRef<AudioContext | null>(null);
  const chunks = useRef<Blob[]>([]);
  const startedAt = useRef(0);
  const timer = useRef<number>(0);
  const mime = useRef<string>("");

  const teardown = useCallback((keepTake: boolean) => {
    window.clearInterval(timer.current);
    timer.current = 0;
    recorder.current = null;
    for (const track of stream.current?.getTracks() ?? []) track.stop();
    stream.current = null;
    setAnalyser(null);
    if (audioCtx.current && audioCtx.current.state !== "closed") {
      void audioCtx.current.close().catch(() => undefined);
    }
    audioCtx.current = null;
    chunks.current = [];
    if (!keepTake) setTake((current) => current); // no-op keeps identity stable
  }, []);

  const start = useCallback(() => {
    if (state === "recording" || state === "requesting") return;
    setTake(null);
    setError(null);

    if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setState("error");
      setError("Voice capture needs a browser with MediaRecorder over https:// or localhost.");
      return;
    }

    setState("requesting");
    navigator.mediaDevices
      .getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } })
      .then((incoming: MediaStream) => {
        stream.current = incoming;
        mime.current = pickMime();
        const r =
          mime.current !== ""
            ? new MediaRecorder(incoming, { mimeType: mime.current })
            : new MediaRecorder(incoming); // browser default (still valid WebAudio blob)
        recorder.current = r;
        chunks.current = [];

        r.ondataavailable = (e: BlobEvent) => {
          if (e.data && e.data.size > 0) chunks.current.push(e.data);
        };
        r.onstop = () => {
          const type = r.mimeType || mime.current || "audio/webm";
          const blob = new Blob(chunks.current, { type });
          const finalChunks = chunks.current;
          chunks.current = [];
          const secondsHeld = Math.max(1, Math.round((Date.now() - startedAt.current) / 1000));
          if (finalChunks.length === 0 || blob.size === 0) {
            setState("error");
            setError("The recording came back empty. Try again, or send text instead.");
            teardown(false);
            return;
          }
          setTake({ blob, mimeType: type, seconds: secondsHeld });
          setState("ready");
          teardown(true);
        };

        /* live level metering */
        const AC: typeof AudioContext | undefined =
          window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
        if (AC) {
          const ctx = new AC();
          audioCtx.current = ctx;
          const src = ctx.createMediaStreamSource(incoming);
          const an = ctx.createAnalyser();
          an.fftSize = 512;
          src.connect(an);
          setAnalyser(an);
        }

        startedAt.current = Date.now();
        setSeconds(0);
        timer.current = window.setInterval(() => {
          setSeconds(Math.max(1, Math.floor((Date.now() - startedAt.current) / 1000)));
        }, 250);
        r.start(400); // chunked so very short takes still flush
        setState("recording");
      })
      .catch((err: DOMException) => {
        if (err.name === "NotAllowedError" || err.name === "SecurityError" || err.name === "PermissionDeniedError") {
          setState("denied");
          setError(null);
        } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
          setState("error");
          setError("No microphone is connected to this device.");
        } else {
          setState("error");
          setError(`Microphone failed: ${err.name ?? "unknown"} — ${err.message ?? ""}`.trim());
        }
      });
  }, [state, teardown]);

  const stop = useCallback(() => {
    const r = recorder.current;
    if (r && state === "recording") r.stop();
  }, [state]);

  const reset = useCallback(() => {
    teardown(false);
    setTake(null);
    setSeconds(0);
    setError(null);
    setState("idle");
  }, [teardown]);

  /* unmount hygiene: release the mic even mid-recording */
  useEffect(
    () => () => {
      const r = recorder.current;
      if (r && r.state === "recording") {
        try {
          r.stop();
        } catch {
          /* already stopped */
        }
      }
      window.clearInterval(timer.current);
      for (const track of stream.current?.getTracks() ?? []) track.stop();
      if (audioCtx.current && audioCtx.current.state !== "closed") void audioCtx.current.close();
    },
    []
  );

  return { state, seconds, take, error, analyser, start, stop, reset };
}

export default useVoiceRecorder;
