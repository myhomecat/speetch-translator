"use client";

import { useEffect, useRef } from "react";
import type { Transcript, RealtimeTranscript } from "@/types";

interface SubtitleDisplayProps {
  transcripts: Transcript[];
  realtimeTranscripts: Map<string, RealtimeTranscript>;
  currentUserId: string | null;
  soloMode?: boolean; // 대면 모드: 큰 자막 + 화자 라벨 중심 표시
}

export function SubtitleDisplay({
  transcripts,
  realtimeTranscripts,
  currentUserId,
  soloMode = false,
}: SubtitleDisplayProps) {
  // 대면 모드는 멀리서도 읽히도록 자막을 키운다
  const textSize = soloMode ? "text-xl md:text-2xl" : "text-sm";
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new transcripts arrive or realtime updates
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [transcripts, realtimeTranscripts]);

  const realtimeArray = Array.from(realtimeTranscripts.values());
  const hasContent = transcripts.length > 0 || realtimeArray.length > 0;
  console.log("[SubtitleDisplay] render - realtimeTranscripts size:", realtimeTranscripts.size, "hasContent:", hasContent);

  if (!hasContent) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400">
        <p>대화가 여기에 표시됩니다</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto space-y-3 p-4"
    >
      {/* 완료된 자막 (번역 포함) */}
      {transcripts.map((transcript) => {
        const isCurrentUser = transcript.userId === currentUserId;

        return (
          <div
            key={transcript.id}
            className={`flex flex-col ${isCurrentUser ? "items-end" : "items-start"}`}
          >
            <span className="text-xs text-gray-500 mb-1">
              {transcript.speaker != null && (
                <span className={`mr-1 px-1.5 py-0.5 rounded font-medium ${getSpeakerColor(transcript.speaker)}`}>
                  화자 {transcript.speaker}
                </span>
              )}
              {transcript.userName}
            </span>

            <div
              className={`
                max-w-[80%] rounded-lg p-3
                ${isCurrentUser ? "bg-blue-100" : "bg-gray-100"}
              `}
            >
              {transcript.originalText && (
                <p className={`${textSize} text-gray-800`}>
                  <span className="text-xs text-gray-500 mr-1">
                    [{getLanguageLabel(transcript.originalLanguage)}]
                  </span>
                  {transcript.originalText}
                </p>
              )}

              {transcript.translatedText && (
                <p className={`${textSize} text-blue-700 mt-1 pt-1 border-t border-gray-200`}>
                  <span className="text-xs text-blue-500 mr-1">
                    [{getLanguageLabel(transcript.translatedLanguage)}]
                  </span>
                  {transcript.translatedText}
                </p>
              )}
            </div>

            <span className="text-xs text-gray-400 mt-1">
              {formatTime(transcript.timestamp)}
            </span>
          </div>
        );
      })}

      {/* 실시간 자막 (말하는 중 / 문장 완료) */}
      {realtimeArray.map((rt) => {
        const isCurrentUser = rt.userId === currentUserId;

        return (
          <div
            key={`realtime-${rt.userId}`}
            className={`flex flex-col ${isCurrentUser ? "items-end" : "items-start"}`}
          >
            <span className="text-xs text-gray-500 mb-1">
              {rt.speaker != null && (
                <span className={`mr-1 px-1.5 py-0.5 rounded font-medium ${getSpeakerColor(rt.speaker)}`}>
                  화자 {rt.speaker}
                </span>
              )}
              {rt.userName}
              {!rt.isFinal && (
                <span className="ml-1 text-green-500 animate-pulse">말하는 중...</span>
              )}
              {rt.isFinal && (
                <span className="ml-1 text-blue-500">번역 완료</span>
              )}
            </span>

            <div
              className={`
                max-w-[80%] rounded-lg p-3 border-2
                ${rt.isFinal ? "border-solid" : "border-dashed"}
                ${isCurrentUser
                  ? (rt.isFinal ? "bg-blue-100 border-blue-400" : "bg-blue-50 border-blue-300")
                  : (rt.isFinal ? "bg-gray-100 border-gray-400" : "bg-gray-50 border-gray-300")
                }
              `}
            >
              {/* 원본 텍스트 (있는 경우) */}
              {rt.text && (
                <p className={`${textSize} ${rt.isFinal ? "text-gray-800" : "text-gray-600 italic"}`}>
                  {rt.sourceLanguage && (
                    <span className="text-xs text-gray-500 mr-1">
                      [{getLanguageLabel(rt.sourceLanguage)}]
                    </span>
                  )}
                  {rt.text}
                </p>
              )}

              {/* 번역된 텍스트 (실시간으로 표시) */}
              {rt.translatedText && (
                <p className={`${textSize} ${rt.isFinal ? "text-blue-700" : "text-green-600 italic"} ${rt.text ? "mt-1 pt-1 border-t border-gray-200" : ""}`}>
                  {rt.targetLanguage && (
                    <span className={`text-xs mr-1 ${rt.isFinal ? "text-blue-500" : "text-green-500"}`}>
                      [{getLanguageLabel(rt.targetLanguage)}]
                    </span>
                  )}
                  {rt.translatedText}
                  {!rt.isFinal && (
                    <span className="inline-block w-1 h-4 ml-1 bg-green-400 animate-pulse" />
                  )}
                </p>
              )}

              {/* 내용이 없는 경우 (로딩 상태) */}
              {!rt.text && !rt.translatedText && (
                <p className="text-sm text-gray-400 italic">
                  처리 중...
                  <span className="inline-block w-1 h-4 ml-1 bg-gray-400 animate-pulse" />
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function getSpeakerColor(speaker: number): string {
  const colors = [
    "bg-purple-100 text-purple-700",
    "bg-amber-100 text-amber-700",
    "bg-teal-100 text-teal-700",
    "bg-rose-100 text-rose-700",
  ];
  return colors[Math.abs(speaker) % colors.length];
}

function getLanguageLabel(lang: string): string {
  switch (lang) {
    case "ko":
      return "한국어";
    case "ja":
      return "日本語";
    case "auto":
      return "자동";
    default:
      return lang;
  }
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
