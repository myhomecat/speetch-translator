"use client";

import { useCallback, useRef, useState } from "react";

interface UseAudioCaptureOptions {
  onAudioData?: (data: ArrayBuffer) => void;
  onSpeechStart?: () => void;
  onSpeechEnd?: () => void;
  useVAD?: boolean; // 음성 감지 사용 여부
  silenceThreshold?: number; // 침묵 임계값 (0-255, 기본 15)
  silenceDuration?: number; // 침묵 지속 시간 (ms, 기본 1500)
}

export function useAudioCapture(options: UseAudioCaptureOptions = {}) {
  const {
    onAudioData,
    onSpeechStart,
    onSpeechEnd,
    useVAD = true,
    silenceThreshold = 15,  // 볼륨 임계값 (0-255)
    silenceDuration = 1500, // 1.5초 침묵 시 말 끝났다고 판단
  } = options;

  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const volumeCheckIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const isSpeakingRef = useRef<boolean>(false);
  const hasSpokenRef = useRef<boolean>(false); // 한 번이라도 말했는지

  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startRecording = useCallback(async () => {
    try {
      setError(null);

      // Check if mediaDevices is available (requires HTTPS or localhost)
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("마이크 접근 불가: HTTPS 또는 localhost에서만 사용 가능합니다");
      }

      // Get microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      // Create audio context
      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;

      // Load audio worklet
      await audioContext.audioWorklet.addModule("/worklet/pcm-processor.js");

      // Create worklet node
      const workletNode = new AudioWorkletNode(audioContext, "pcm-processor");
      workletNodeRef.current = workletNode;

      // Handle audio data from worklet
      workletNode.port.onmessage = (event) => {
        onAudioData?.(event.data);
      };

      // Connect microphone to worklet
      const source = audioContext.createMediaStreamSource(stream);
      sourceRef.current = source;
      source.connect(workletNode);

      // 볼륨 기반 음성 감지 (useVAD가 true일 때만)
      if (useVAD) {
        // Create analyser for volume detection
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        analyserRef.current = analyser;
        source.connect(analyser);

        const dataArray = new Uint8Array(analyser.frequencyBinCount);

        // 볼륨 체크 인터벌 (50ms마다)
        volumeCheckIntervalRef.current = setInterval(() => {
          if (!analyserRef.current) return;

          analyser.getByteFrequencyData(dataArray);

          // 평균 볼륨 계산
          const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;

          if (average > silenceThreshold) {
            // 소리 감지됨
            if (!isSpeakingRef.current) {
              console.log(`[Volume VAD] Speech started (volume: ${average.toFixed(1)})`);
              isSpeakingRef.current = true;
              hasSpokenRef.current = true;
              setIsSpeaking(true);
              onSpeechStart?.();
            }

            // 침묵 타이머 리셋
            if (silenceTimerRef.current) {
              clearTimeout(silenceTimerRef.current);
              silenceTimerRef.current = null;
            }
          } else {
            // 조용함 - 침묵 타이머 시작 (이미 말을 시작한 경우에만)
            if (isSpeakingRef.current && !silenceTimerRef.current) {
              silenceTimerRef.current = setTimeout(() => {
                console.log(`[Volume VAD] Speech ended (silence for ${silenceDuration}ms)`);
                isSpeakingRef.current = false;
                setIsSpeaking(false);
                onSpeechEnd?.();
                silenceTimerRef.current = null;
              }, silenceDuration);
            }
          }
        }, 50);

        console.log("[Volume VAD] Volume-based voice detection started");
      }

      setIsRecording(true);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to start recording";
      setError(message);
      console.error("Error starting recording:", err);
    }
  }, [onAudioData, onSpeechStart, onSpeechEnd, useVAD, silenceThreshold, silenceDuration]);

  const stopRecording = useCallback(() => {
    // Clear timers
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (volumeCheckIntervalRef.current) {
      clearInterval(volumeCheckIntervalRef.current);
      volumeCheckIntervalRef.current = null;
    }

    // Disconnect analyser
    if (analyserRef.current) {
      analyserRef.current.disconnect();
      analyserRef.current = null;
    }

    // Disconnect nodes
    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }

    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }

    // Stop media stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    // Close audio context
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    isSpeakingRef.current = false;
    hasSpokenRef.current = false;
    setIsSpeaking(false);
    setIsRecording(false);
  }, []);

  return {
    isRecording,
    isSpeaking,  // 음성 감지 상태
    error,
    startRecording,
    stopRecording,
  };
}
