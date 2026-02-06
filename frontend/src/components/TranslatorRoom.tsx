"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { v4 as uuidv4 } from "uuid";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useAudioCapture } from "@/hooks/useAudioCapture";
import { useAudioPlayback } from "@/hooks/useAudioPlayback";
import { LanguageSelector } from "./LanguageSelector";
import { SubtitleDisplay } from "./SubtitleDisplay";
import { UserList } from "./UserList";
import { MAX_TRANSCRIPTS } from "@/lib/constants";
import type {
  TranslationMode,
  ServerMessage,
  UserInfo,
  Transcript,
  RealtimeTranscript,
} from "@/types";

interface TranslatorRoomProps {
  roomId: string;
  userName: string;
}

export function TranslatorRoom({ roomId, userName }: TranslatorRoomProps) {
  const [translationMode, setTranslationMode] = useState<TranslationMode>("auto");
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [userId, setUserId] = useState<string | null>(null);
  const [transcripts, setTranscripts] = useState<Transcript[]>([]);
  const [realtimeTranscripts, setRealtimeTranscripts] = useState<Map<string, RealtimeTranscript>>(new Map());
  const realtimeTimersRef = useRef<Map<string, NodeJS.Timeout>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [showParticipants, setShowParticipants] = useState(false);

  const { playAudio, stopPlayback } = useAudioPlayback();

  const handleMessage = useCallback((message: ServerMessage) => {
    switch (message.type) {
      case "room_info":
        setUserId(message.user_id);
        setUsers(message.users);
        break;

      case "user_joined":
        setUsers((prev) => [...prev, message.user]);
        break;

      case "user_left":
        setUsers((prev) => prev.filter((u) => u.id !== message.user_id));
        break;

      case "transcript":
        if (message.original_text || message.translated_text) {
          setTranscripts((prev) => {
            const newTranscript: Transcript = {
              id: uuidv4(),
              userId: message.user_id,
              userName: message.user_name,
              originalText: message.original_text,
              originalLanguage: message.original_language,
              translatedText: message.translated_text || "",
              translatedLanguage: message.translated_language || "",
              timestamp: new Date(),
            };

            const updated = [...prev, newTranscript];
            // Keep only last N transcripts
            if (updated.length > MAX_TRANSCRIPTS) {
              return updated.slice(-MAX_TRANSCRIPTS);
            }
            return updated;
          });
        }
        break;

      case "realtime_transcript":
        // 실시간 자막 (말하는 중 / 문장 완료)
        console.log("[TranslatorRoom] realtime_transcript received:", message);
        setRealtimeTranscripts((prev) => {
          console.log("[TranslatorRoom] Updating realtimeTranscripts, prev size:", prev.size);
          const newMap = new Map(prev);
          const existingRT = prev.get(message.user_id);

          if (message.is_final) {
            // 문장이 완료되면 누적된 텍스트에 마지막 토큰 추가
            const finalText = existingRT?.text
              ? (message.text ? existingRT.text + message.text : existingRT.text)
              : (message.text || "");
            const finalTranslated = existingRT?.translatedText
              ? (message.translated_text ? existingRT.translatedText + message.translated_text : existingRT.translatedText)
              : (message.translated_text || "");

            newMap.set(message.user_id, {
              userId: message.user_id,
              userName: message.user_name,
              text: finalText,
              translatedText: finalTranslated,
              sourceLanguage: message.source_language,
              targetLanguage: message.target_language,
              isFinal: true,
              timestamp: new Date(),
            });
            // 10초 후 제거 (메모리 누수 방지: 타이머 관리)
            const targetUserId = message.user_id; // 클로저에서 필요한 값만 캡처

            // 기존 타이머가 있으면 취소
            const existingTimer = realtimeTimersRef.current.get(targetUserId);
            if (existingTimer) {
              clearTimeout(existingTimer);
            }

            // 새 타이머 생성 및 저장
            const timerId = setTimeout(() => {
              setRealtimeTranscripts((current) => {
                const updated = new Map(current);
                updated.delete(targetUserId);
                return updated;
              });
              realtimeTimersRef.current.delete(targetUserId);
            }, 10000);

            realtimeTimersRef.current.set(targetUserId, timerId);
          } else {
            // 말하는 중이면 텍스트 대체 (Soniox는 전체 텍스트를 보내므로 누적하지 않음)
            const prevText = existingRT?.isFinal ? "" : (existingRT?.text || "");
            const prevTranslated = existingRT?.isFinal ? "" : (existingRT?.translatedText || "");

            newMap.set(message.user_id, {
              userId: message.user_id,
              userName: message.user_name,
              // Soniox는 partial 결과로 전체 텍스트를 보내므로 대체함
              text: message.text || prevText,
              translatedText: message.translated_text || prevTranslated,
              sourceLanguage: message.source_language || existingRT?.sourceLanguage || null,
              targetLanguage: message.target_language || existingRT?.targetLanguage || null,
              isFinal: false,
              timestamp: new Date(),
            });
          }
          return newMap;
        });
        break;

      case "error":
        setError(message.message);
        break;
    }
  }, []);

  // 컴포넌트 언마운트 시 모든 타이머 정리
  useEffect(() => {
    return () => {
      realtimeTimersRef.current.forEach((timerId) => {
        clearTimeout(timerId);
      });
      realtimeTimersRef.current.clear();
    };
  }, []);

  const handleAudioData = useCallback(
    (data: ArrayBuffer) => {
      playAudio(data);
    },
    [playAudio]
  );

  const handleError = useCallback((errorMsg: string) => {
    setError(errorMsg);
  }, []);

  const {
    isConnected,
    connect,
    disconnect,
    sendAudio,
    changeMode,
    resetSession,
    endAudioStream,
  } = useWebSocket({
    roomId,
    userName,
    translationMode,
    onMessage: handleMessage,
    onAudioData: handleAudioData,
    onError: handleError,
  });

  const handleAudioCapture = useCallback(
    (data: ArrayBuffer) => {
      sendAudio(data);
    },
    [sendAudio]
  );

  // 침묵 감지 시 end_turn 전송
  const handleSpeechEnd = useCallback(() => {
    console.log("[TranslatorRoom] Speech ended - sending end_turn");
    endAudioStream();
  }, [endAudioStream]);

  const {
    isRecording,
    isSpeaking,
    error: captureError,
    startRecording,
    stopRecording: stopAudioCapture,
  } = useAudioCapture({
    onAudioData: handleAudioCapture,
    onSpeechEnd: handleSpeechEnd,  // 침묵 감지 시 호출
    useVAD: true,  // 볼륨 기반 음성 감지 활성화
    silenceThreshold: 15,  // 볼륨 임계값 (0-255)
    silenceDuration: 1500,  // 1.5초 침묵 시 말 끝났다고 판단
  });

  const handleStopRecording = useCallback(() => {
    stopAudioCapture();
    // 마이크 끌 때도 end_turn 전송 (아직 말하는 중이었을 경우)
    endAudioStream();
    // 세션 리셋 제거 - Gemini는 연속 대화 세션이므로 리셋 불필요
  }, [stopAudioCapture, endAudioStream]);

  const handleModeChange = useCallback(
    (mode: TranslationMode) => {
      setTranslationMode(mode);
      if (isConnected) {
        changeMode(mode);
      }
    },
    [isConnected, changeMode]
  );

  // Connect on mount only (empty dependency array to prevent reconnection loops)
  useEffect(() => {
    connect();
    return () => {
      stopAudioCapture();
      stopPlayback();
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const displayError = error || captureError;

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm px-6 py-4">
        <div className="flex items-center justify-between max-w-6xl mx-auto">
          <div>
            <h1 className="text-xl font-bold text-gray-900">
              음성 번역 채팅방
            </h1>
            <p className="text-sm text-gray-500">
              방 코드: <span className="font-mono font-medium">{roomId}</span>
            </p>
          </div>

          <div className="flex items-center gap-4">
            <LanguageSelector
              value={translationMode}
              onChange={handleModeChange}
              disabled={isRecording}
            />

            <div
              className={`
                px-3 py-1 rounded-full text-sm font-medium
                ${isConnected ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}
              `}
            >
              {isConnected ? "연결됨" : "연결 중..."}
            </div>
          </div>
        </div>
      </header>

      {/* Error Banner */}
      {displayError && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4">
          <div className="flex">
            <div className="ml-3">
              <p className="text-sm text-red-700">{displayError}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="ml-auto text-red-500 hover:text-red-700"
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* Main Content - 대화 내용이 전체 차지 */}
      <div className="flex-1 min-h-0 flex flex-col max-w-6xl mx-auto w-full p-4 md:p-6 overflow-hidden relative pb-20">
        {/* Subtitle Area */}
        <div className="flex-1 min-h-0 bg-white rounded-xl shadow-sm flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100">
            <h2 className="font-medium text-gray-700">대화 내용</h2>
          </div>
          <SubtitleDisplay
            transcripts={transcripts}
            realtimeTranscripts={realtimeTranscripts}
            currentUserId={userId}
          />
        </div>

        {/* 참가자 목록 팝업 */}
        {showParticipants && (
          <div className="absolute bottom-24 left-4 right-4 md:left-auto md:right-6 md:w-72 bg-white rounded-xl shadow-lg z-10">
            <UserList users={users} currentUserId={userId} />
          </div>
        )}
      </div>

      {/* 하단 고정 바 */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg z-20">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          {/* 참가자 토글 버튼 */}
          <button
            onClick={() => setShowParticipants(!showParticipants)}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-colors
              ${showParticipants ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}
            `}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
            </svg>
            <span>{users.length}/3</span>
          </button>

          {/* 마이크 버튼 */}
          <button
            onClick={isRecording ? handleStopRecording : startRecording}
            disabled={!isConnected}
            className={`
              w-16 h-16 rounded-full flex items-center justify-center transition-all transform
              ${!isConnected
                ? "bg-gray-300 cursor-not-allowed"
                : isRecording
                  ? "bg-red-500 hover:bg-red-600 scale-110 animate-pulse"
                  : "bg-blue-500 hover:bg-blue-600 hover:scale-105"
              }
            `}
          >
            {isRecording ? (
              <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
                <rect x="6" y="6" width="12" height="12" rx="2" />
              </svg>
            ) : (
              <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
            )}
          </button>

          {/* 녹음 상태 표시 */}
          <div className="w-20 text-center">
            {isRecording && (
              <span className={`text-sm font-medium ${isSpeaking ? "text-green-600" : "text-orange-500"}`}>
                {isSpeaking ? "말하는 중..." : "대기 중..."}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
