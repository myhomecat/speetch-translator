export type TranslationMode = "auto" | "ko_to_ja" | "ja_to_ko";

export type MessageType =
  | "join"
  | "leave"
  | "audio_data"
  | "transcript"
  | "realtime_transcript"
  | "error"
  | "room_info"
  | "mode_change"
  | "user_joined"
  | "user_left";

export interface UserInfo {
  id: string;
  name: string;
  translation_mode: TranslationMode;
}

export interface RoomInfoMessage {
  type: "room_info";
  room_id: string;
  user_id: string;
  users: UserInfo[];
}

export interface UserJoinedMessage {
  type: "user_joined";
  user: UserInfo;
}

export interface UserLeftMessage {
  type: "user_left";
  user_id: string;
  user_name: string;
}

export interface TranscriptMessage {
  type: "transcript";
  user_id: string;
  user_name: string;
  original_text: string;
  original_language: string;
  translated_text: string | null;
  translated_language: string | null;
  speaker?: number | null; // 화자 번호 (diarization)
}

export interface ErrorMessage {
  type: "error";
  message: string;
  code?: string;
}

export interface RealtimeTranscriptMessage {
  type: "realtime_transcript";
  user_id: string;
  user_name: string;
  text: string;
  is_final: boolean;
  translated_text: string | null;
  source_language: string | null;
  target_language: string | null;
  speaker?: number | null; // 화자 번호 (diarization)
}

export type ServerMessage =
  | RoomInfoMessage
  | UserJoinedMessage
  | UserLeftMessage
  | TranscriptMessage
  | RealtimeTranscriptMessage
  | ErrorMessage;

export interface JoinMessage {
  type: "join";
  user_name: string;
  translation_mode: TranslationMode;
}

export interface ModeChangeMessage {
  type: "mode_change";
  translation_mode: TranslationMode;
}

export type ClientMessage = JoinMessage | ModeChangeMessage;

export interface Transcript {
  id: string;
  userId: string;
  userName: string;
  originalText: string;
  originalLanguage: string;
  translatedText: string;
  translatedLanguage: string;
  timestamp: Date;
  speaker?: number | null; // 화자 번호 (diarization)
}

export interface RealtimeTranscript {
  userId: string;
  userName: string;
  text: string;
  translatedText: string | null;
  sourceLanguage: string | null;
  targetLanguage: string | null;
  isFinal: boolean;
  timestamp: Date;
  speaker?: number | null; // 화자 번호 (diarization)
}

export interface RoomState {
  roomId: string | null;
  userId: string | null;
  users: UserInfo[];
  transcripts: Transcript[];
  isConnected: boolean;
  isRecording: boolean;
  error: string | null;
}
