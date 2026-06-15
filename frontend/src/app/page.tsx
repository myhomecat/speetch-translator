"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useConfig } from "@/lib/config-context";

export default function Home() {
  const router = useRouter();
  const { API_URL } = useConfig();
  const [userName, setUserName] = useState("");
  const [roomCode, setRoomCode] = useState("");
  const [password, setPassword] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [isJoining, setIsJoining] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const CORRECT_PASSWORD = "arisa";

  const handleCreateRoom = async () => {
    if (!userName.trim()) {
      setError("이름을 입력해주세요");
      return;
    }

    if (password !== CORRECT_PASSWORD) {
      setError("비밀번호가 틀렸습니다");
      return;
    }

    setIsCreating(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/rooms/create`, {
        method: "POST",
      });
      const data = await response.json();

      // Store user name in session storage
      sessionStorage.setItem("userName", userName.trim());
      router.push(`/room/${data.room_id}`);
    } catch (err) {
      setError("방 생성에 실패했습니다. 서버 연결을 확인해주세요.");
    } finally {
      setIsCreating(false);
    }
  };

  const handleJoinRoom = async () => {
    if (!userName.trim()) {
      setError("이름을 입력해주세요");
      return;
    }

    if (password !== CORRECT_PASSWORD) {
      setError("비밀번호가 틀렸습니다");
      return;
    }

    if (!roomCode.trim()) {
      setError("방 코드를 입력해주세요");
      return;
    }

    setIsJoining(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/rooms/${roomCode.trim()}/exists`);
      const data = await response.json();

      if (!data.available) {
        setError("방이 꽉 찼거나 존재하지 않습니다");
        return;
      }

      sessionStorage.setItem("userName", userName.trim());
      router.push(`/room/${roomCode.trim()}`);
    } catch (err) {
      setError("방 참가에 실패했습니다. 서버 연결을 확인해주세요.");
    } finally {
      setIsJoining(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-purple-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            음성 번역기
          </h1>
          <p className="text-gray-600">
            실시간 한국어-일본어 동시 번역
          </p>
        </div>

        {error && (
          <div className="bg-red-50 text-red-600 p-3 rounded-lg mb-6 text-sm">
            {error}
          </div>
        )}

        <div className="space-y-6">
          {/* User Name Input */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              이름
            </label>
            <input
              type="text"
              value={userName}
              onChange={(e) => setUserName(e.target.value)}
              placeholder="표시될 이름을 입력하세요"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
              maxLength={20}
            />
          </div>

          {/* Password Input */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              비밀번호
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="비밀번호를 입력하세요"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
            />
          </div>

          {/* Create Room */}
          <button
            onClick={handleCreateRoom}
            disabled={isCreating || isJoining}
            className="w-full bg-blue-500 text-white py-3 rounded-lg font-medium hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {isCreating ? "생성 중..." : "새 방 만들기"}
          </button>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-200" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-4 bg-white text-gray-500">또는</span>
            </div>
          </div>

          {/* Join Room */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              방 코드
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={roomCode}
                onChange={(e) => setRoomCode(e.target.value)}
                placeholder="방 코드 입력"
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
                maxLength={20}
              />
              <button
                onClick={handleJoinRoom}
                disabled={isCreating || isJoining}
                className="px-6 py-3 bg-gray-800 text-white rounded-lg font-medium hover:bg-gray-900 disabled:opacity-50 disabled:cursor-not-allowed transition"
              >
                {isJoining ? "..." : "참가"}
              </button>
            </div>
          </div>
        </div>

        <div className="mt-8 pt-6 border-t border-gray-100 text-center text-sm text-gray-500">
          <p>최대 3명까지 동시 접속 가능</p>
          <p className="mt-1">한국어 ↔ 일본어 실시간 음성 번역</p>
        </div>
      </div>
    </div>
  );
}
