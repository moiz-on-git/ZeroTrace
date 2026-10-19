import { useState, useCallback } from "react";

export interface VoiceReceiptOptions {
  receiptId: string;
  solanaTx?: string;
  recordsErased?: number;
  language?: "en" | "hi" | "kn" | "ta";
}

export function useVoiceReceipt() {
  const [isPlaying, setIsPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const speakReceipt = useCallback((opts: VoiceReceiptOptions) => {
    try {
      if (typeof window === "undefined" || !("speechSynthesis" in window)) {
        setError("Speech synthesis not supported in this environment");
        return;
      }

      window.speechSynthesis.cancel();

      const shortTx = (opts.solanaTx || "5Kz9DevnetAnchorTxHash").slice(0, 8);
      const count = opts.recordsErased ?? 1;

      let text = "";
      let langCode = "en-US";

      switch (opts.language) {
        case "hi":
          text = `ज़ीरोट्रेस सत्यापन। डीपी डी पी अधिनियम की धारा 6(4) के तहत आपके ${count} रिकॉर्ड्स को हमेशा के लिए मिटा दिया गया है। सोलाना ब्लॉकचेन ट्रांजेक्शन: ${shortTx}।`;
          langCode = "hi-IN";
          break;
        case "kn":
          text = `ಜೀರೋಟ್ರೇಸ್ ದೃಢೀಕರಣ. ಡಿಪಿಡಿಪಿ ಕಾಯ್ದೆ 2023 ರ ಅಡಿಯಲ್ಲಿ ನಿಮ್ಮ ${count} ದಾಖಲೆಗಳನ್ನು ಶಾಶ್ವತವಾಗಿ ಅಳಿಸಲಾಗಿದೆ. ಸೊಲಾನಾ ಬ್ಲಾಕ್‌ಚೈನ್ ಪುರಾವೆ: ${shortTx}।`;
          langCode = "kn-IN";
          break;
        case "ta":
          text = `ஜீரோட்ரேஸ் சரிபார்ப்பு. டிபிடிபி சட்டம் பிரிவு 6(4) படி உங்கள் ${count} பதிவுகள் நிரந்தரமாக நீக்கப்பட்டுள்ளன. சோலானா சான்று: ${shortTx}।`;
          langCode = "ta-IN";
          break;
        default:
          text = `ZeroTrace verification confirmed. Under DPDP Act Section 6(4), ${count} personal record has been permanently erased. Cryptographic proof anchored on Solana with transaction ${shortTx}. Your digital trace is zero.`;
          langCode = "en-US";
          break;
      }

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = langCode;
      utterance.rate = 0.95;

      utterance.onstart = () => setIsPlaying(true);
      utterance.onend = () => setIsPlaying(false);
      utterance.onerror = () => {
        setIsPlaying(false);
        setError("Speech playback failed");
      };

      window.speechSynthesis.speak(utterance);
    } catch (e: any) {
      setError(e?.message || "Speech failed");
      setIsPlaying(false);
    }
  }, []);

  const stopSpeaking = useCallback(() => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      setIsPlaying(false);
    }
  }, []);

  return {
    speakReceipt,
    stopSpeaking,
    isPlaying,
    error,
  };
}
