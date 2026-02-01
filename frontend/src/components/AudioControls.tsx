"use client";

interface AudioControlsProps {
  isRecording: boolean;
  isSpeaking?: boolean;  // VAD 음성 감지 상태
  isConnected: boolean;
  onStartRecording: () => void;
  onStopRecording: () => void;
  disabled?: boolean;
}

export function AudioControls({
  isRecording,
  isSpeaking = false,
  isConnected,
  onStartRecording,
  onStopRecording,
  disabled = false,
}: AudioControlsProps) {
  const handleClick = () => {
    if (isRecording) {
      onStopRecording();
    } else {
      onStartRecording();
    }
  };

  // 버튼 색상 결정
  const getButtonColor = () => {
    if (!isRecording) return "bg-blue-500 hover:bg-blue-600";
    if (isSpeaking) return "bg-green-500 hover:bg-green-600 animate-pulse"; // 음성 감지 중
    return "bg-red-500 hover:bg-red-600"; // 녹음 중이지만 침묵
  };

  // 상태 텍스트
  const getStatusText = () => {
    if (!isConnected) return "연결 중...";
    if (!isRecording) return "클릭하여 말하기";
    if (isSpeaking) return "🎤 음성 감지 중... (전송 중)";
    return "⏸️ 대기 중... (말씀해 주세요)";
  };

  return (
    <div className="flex flex-col items-center gap-4">
      <button
        onClick={handleClick}
        disabled={disabled || !isConnected}
        className={`
          w-24 h-24 rounded-full flex items-center justify-center
          transition-all duration-200 ease-in-out
          ${getButtonColor()}
          ${disabled || !isConnected ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
          text-white shadow-lg
        `}
      >
        {isRecording ? (
          isSpeaking ? (
            <VoiceWaveIcon className="w-10 h-10" />
          ) : (
            <MicIcon className="w-10 h-10" />
          )
        ) : (
          <MicIcon className="w-10 h-10" />
        )}
      </button>

      <p className="text-sm text-gray-600">
        {getStatusText()}
      </p>
    </div>
  );
}

function MicIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
      />
    </svg>
  );
}

function StopIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="currentColor"
      viewBox="0 0 24 24"
    >
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  );
}

function VoiceWaveIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="currentColor"
      viewBox="0 0 24 24"
    >
      <rect x="4" y="10" width="2" height="4" rx="1" className="animate-bounce" style={{ animationDelay: "0ms" }} />
      <rect x="8" y="7" width="2" height="10" rx="1" className="animate-bounce" style={{ animationDelay: "150ms" }} />
      <rect x="12" y="4" width="2" height="16" rx="1" className="animate-bounce" style={{ animationDelay: "300ms" }} />
      <rect x="16" y="7" width="2" height="10" rx="1" className="animate-bounce" style={{ animationDelay: "150ms" }} />
      <rect x="20" y="10" width="2" height="4" rx="1" className="animate-bounce" style={{ animationDelay: "0ms" }} />
    </svg>
  );
}
