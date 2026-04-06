export const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const AUDIO_CONFIG = {
  INPUT_SAMPLE_RATE: 16000,  // Client -> Server
  OUTPUT_SAMPLE_RATE: 16000, // Server -> Client (원본 음성 그대로)
  CHANNELS: 1,
  BIT_DEPTH: 16,
} as const;

export const TRANSLATION_MODES = [
  { value: "auto", label: "자동 감지", description: "한국어/일본어 자동 감지" },
  { value: "ko_to_ja", label: "한→일", description: "한국어 → 일본어" },
  { value: "ja_to_ko", label: "일→한", description: "일본어 → 한국어" },
] as const;

export const MAX_USERS_PER_ROOM = 4;
export const MAX_TRANSCRIPTS = 100;
