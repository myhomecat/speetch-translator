"use client";

import type { UserInfo } from "@/types";

interface UserListProps {
  users: UserInfo[];
  currentUserId: string | null;
}

export function UserList({ users, currentUserId }: UserListProps) {
  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-700 mb-3">
        참가자 ({users.length}/3)
      </h3>
      <div className="space-y-2">
        {users.map((user) => (
          <div
            key={user.id}
            className={`
              flex items-center gap-2 p-2 rounded-lg
              ${user.id === currentUserId ? "bg-blue-100" : "bg-white"}
            `}
          >
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-400 to-purple-500 flex items-center justify-center text-white text-sm font-medium">
              {user.name.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">
                {user.name}
                {user.id === currentUserId && (
                  <span className="text-xs text-blue-500 ml-1">(나)</span>
                )}
              </p>
              <p className="text-xs text-gray-500">
                {getModeLabel(user.translation_mode)}
              </p>
            </div>
            <div className="w-2 h-2 rounded-full bg-green-400" title="온라인" />
          </div>
        ))}
      </div>
    </div>
  );
}

function getModeLabel(mode: string): string {
  switch (mode) {
    case "auto":
      return "자동 감지";
    case "ko_to_ja":
      return "한→일";
    case "ja_to_ko":
      return "일→한";
    default:
      return mode;
  }
}
