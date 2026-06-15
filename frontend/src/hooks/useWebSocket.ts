"use client";

import { useCallback, useRef, useState, useEffect } from "react";
import { useConfig } from "@/lib/config-context";
import type {
  TranslationMode,
  ServerMessage,
  JoinMessage,
  ModeChangeMessage,
} from "@/types";

interface UseWebSocketOptions {
  roomId: string;
  userName: string;
  translationMode: TranslationMode;
  onMessage?: (message: ServerMessage) => void;
  onAudioData?: (data: ArrayBuffer) => void;
  onConnected?: () => void;
  onDisconnected?: () => void;
  onError?: (error: string) => void;
}

// Keepalive interval (20 seconds)
const KEEPALIVE_INTERVAL = 20000;

export function useWebSocket(options: UseWebSocketOptions) {
  const { WS_URL } = useConfig();
  const {
    roomId,
    userName,
    translationMode,
    onMessage,
    onAudioData,
    onConnected,
    onDisconnected,
    onError,
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const isConnectingRef = useRef(false);
  const keepaliveIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Use refs to store callbacks to avoid reconnection on callback changes
  const onMessageRef = useRef(onMessage);
  const onAudioDataRef = useRef(onAudioData);
  const onConnectedRef = useRef(onConnected);
  const onDisconnectedRef = useRef(onDisconnected);
  const onErrorRef = useRef(onError);

  // Update refs when callbacks change
  useEffect(() => {
    onMessageRef.current = onMessage;
    onAudioDataRef.current = onAudioData;
    onConnectedRef.current = onConnected;
    onDisconnectedRef.current = onDisconnected;
    onErrorRef.current = onError;
  }, [onMessage, onAudioData, onConnected, onDisconnected, onError]);

  // Start keepalive ping to prevent connection timeout
  const startKeepalive = useCallback(() => {
    stopKeepalive();
    keepaliveIntervalRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "ping" }));
      }
    }, KEEPALIVE_INTERVAL);
  }, []);

  // Stop keepalive ping
  const stopKeepalive = useCallback(() => {
    if (keepaliveIntervalRef.current) {
      clearInterval(keepaliveIntervalRef.current);
      keepaliveIntervalRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || isConnectingRef.current) {
      return;
    }

    // Close existing connection if any
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    stopKeepalive();

    isConnectingRef.current = true;
    const ws = new WebSocket(`${WS_URL}/ws/${roomId}`);
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
      // Send join message
      const joinMessage: JoinMessage = {
        type: "join",
        user_name: userName,
        translation_mode: translationMode,
      };
      ws.send(JSON.stringify(joinMessage));
      // Start keepalive after connection
      startKeepalive();
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        // Binary audio data
        console.log("[WS] Received audio data:", event.data.byteLength, "bytes");
        onAudioDataRef.current?.(event.data);
      } else {
        // JSON message
        try {
          const message: ServerMessage = JSON.parse(event.data);
          console.log("[WS] Received message:", message.type, message);

          if (message.type === "room_info") {
            isConnectingRef.current = false;
            setIsConnected(true);
            onConnectedRef.current?.();
          } else if (message.type === "error") {
            onErrorRef.current?.(message.message);
          }

          onMessageRef.current?.(message);
        } catch (e) {
          console.error("Failed to parse message:", e);
        }
      }
    };

    ws.onclose = () => {
      // Only handle if this is still the current websocket
      if (wsRef.current === ws) {
        isConnectingRef.current = false;
        setIsConnected(false);
        stopKeepalive();
        onDisconnectedRef.current?.();
      }
    };

    ws.onerror = () => {
      // Only report error if this is still the current websocket
      if (wsRef.current === ws) {
        isConnectingRef.current = false;
        onErrorRef.current?.("WebSocket connection error");
      }
    };

    wsRef.current = ws;
  }, [roomId, userName, translationMode, startKeepalive, stopKeepalive]);

  const disconnect = useCallback(() => {
    isConnectingRef.current = false;
    stopKeepalive();
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, [stopKeepalive]);

  const sendAudio = useCallback((data: ArrayBuffer) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    }
  }, []);

  const sendMessage = useCallback((message: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const changeMode = useCallback((mode: TranslationMode) => {
    sendMessage({
      type: "mode_change",
      translation_mode: mode,
    });
  }, [sendMessage]);

  const resetSession = useCallback(() => {
    sendMessage({
      type: "reset_session",
    });
  }, [sendMessage]);

  const endAudioStream = useCallback(() => {
    sendMessage({
      type: "end_audio_stream",
    });
  }, [sendMessage]);

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    isConnected,
    connect,
    disconnect,
    sendAudio,
    changeMode,
    resetSession,
    endAudioStream,
  };
}
