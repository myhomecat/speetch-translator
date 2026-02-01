"use client";

import { useCallback, useRef } from "react";
import { AUDIO_CONFIG } from "@/lib/constants";

export function useAudioPlayback() {
  const audioContextRef = useRef<AudioContext | null>(null);
  const nextStartTimeRef = useRef<number>(0);

  const getAudioContext = useCallback(() => {
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext({
        sampleRate: AUDIO_CONFIG.OUTPUT_SAMPLE_RATE,
      });
    }
    return audioContextRef.current;
  }, []);

  const playAudio = useCallback(
    async (audioData: ArrayBuffer) => {
      const audioContext = getAudioContext();

      // Resume audio context if suspended
      if (audioContext.state === "suspended") {
        await audioContext.resume();
      }

      // Convert PCM data to AudioBuffer
      const int16Array = new Int16Array(audioData);
      const float32Array = new Float32Array(int16Array.length);

      // Convert 16-bit PCM to float32
      for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768;
      }

      // Create audio buffer
      const audioBuffer = audioContext.createBuffer(
        1, // mono
        float32Array.length,
        AUDIO_CONFIG.OUTPUT_SAMPLE_RATE
      );
      audioBuffer.getChannelData(0).set(float32Array);

      // Create buffer source
      const source = audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContext.destination);

      // Schedule playback with proper timing to avoid gaps
      const currentTime = audioContext.currentTime;
      const startTime = Math.max(currentTime, nextStartTimeRef.current);

      source.start(startTime);
      nextStartTimeRef.current = startTime + audioBuffer.duration;
    },
    [getAudioContext]
  );

  const stopPlayback = useCallback(() => {
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    nextStartTimeRef.current = 0;
  }, []);

  return {
    playAudio,
    stopPlayback,
  };
}
