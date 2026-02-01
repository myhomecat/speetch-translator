"use client";

import { useRef, useState, useCallback } from "react";
import { AUDIO_CONFIG } from "@/lib/constants";

interface AudioFileUploadProps {
  onAudioData: (data: ArrayBuffer) => void;
  onAudioStreamEnd?: () => void;
  disabled?: boolean;
}

export function AudioFileUpload({ onAudioData, onAudioStreamEnd, disabled }: AudioFileUploadProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);

  const processAudioFile = useCallback(async (file: File) => {
    setIsProcessing(true);
    setFileName(file.name);

    try {
      const arrayBuffer = await file.arrayBuffer();
      const audioContext = new AudioContext();
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);

      // Resample to 16kHz mono
      const offlineContext = new OfflineAudioContext(
        1, // mono
        Math.ceil(audioBuffer.duration * AUDIO_CONFIG.INPUT_SAMPLE_RATE),
        AUDIO_CONFIG.INPUT_SAMPLE_RATE
      );

      const source = offlineContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(offlineContext.destination);
      source.start();

      const resampledBuffer = await offlineContext.startRendering();
      const pcmData = resampledBuffer.getChannelData(0);

      // Convert to 16-bit PCM and send in chunks
      const chunkSize = AUDIO_CONFIG.INPUT_SAMPLE_RATE * 0.1; // 100ms chunks

      for (let i = 0; i < pcmData.length; i += chunkSize) {
        const chunk = pcmData.slice(i, Math.min(i + chunkSize, pcmData.length));
        const int16Array = new Int16Array(chunk.length);

        for (let j = 0; j < chunk.length; j++) {
          const s = Math.max(-1, Math.min(1, chunk[j]));
          int16Array[j] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }

        onAudioData(int16Array.buffer);

        // Small delay between chunks
        await new Promise(r => setTimeout(r, 50));
      }

      // Signal end of audio stream
      if (onAudioStreamEnd) {
        onAudioStreamEnd();
      }

      await audioContext.close();
    } catch (err) {
      const error = err as Error;
      console.error("Error processing audio file:", error.name, error.message, error.stack);

      // 특정 오류 유형에 대한 사용자 친화적 메시지
      if (error.name === "EncodingError" || error.message.includes("decode")) {
        alert(
          `이 오디오 파일 형식을 처리할 수 없습니다.\n\n` +
          `지원되는 형식: WAV, MP3, OGG, WebM\n` +
          `m4a/AAC 파일은 일부 브라우저에서 지원되지 않습니다.\n\n` +
          `해결 방법:\n` +
          `- WAV 또는 MP3로 변환 후 업로드해 주세요\n` +
          `- 온라인 변환 도구: https://cloudconvert.com/m4a-to-wav`
        );
      } else {
        alert(`오디오 파일 처리 중 오류가 발생했습니다: ${error.message || error}`);
      }
    } finally {
      setIsProcessing(false);
    }
  }, [onAudioData, onAudioStreamEnd]);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      processAudioFile(file);
    }
  }, [processAudioFile]);

  const handleClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  return (
    <div className="w-full">
      <label
        className={`
          relative block w-full px-4 py-2 rounded-lg text-sm font-medium transition text-center cursor-pointer
          ${disabled || isProcessing
            ? "bg-gray-100 text-gray-400 cursor-not-allowed"
            : "bg-gray-200 text-gray-700 hover:bg-gray-300"
          }
        `}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*,.wav,.mp3,.ogg,.webm"
          onChange={handleFileChange}
          disabled={disabled || isProcessing}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />
        {isProcessing ? (
          <span className="flex items-center justify-center gap-2">
            <span className="animate-spin h-4 w-4 border-2 border-gray-500 border-t-transparent rounded-full" />
            처리 중...
          </span>
        ) : (
          "오디오 파일 업로드 (WAV/MP3/OGG)"
        )}
      </label>
      {fileName && !isProcessing && (
        <p className="text-xs text-gray-500 mt-1 text-center truncate">
          {fileName}
        </p>
      )}
    </div>
  );
}
