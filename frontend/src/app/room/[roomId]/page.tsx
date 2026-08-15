"use client";

import { useEffect, useState, Suspense } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { TranslatorRoom } from "@/components/TranslatorRoom";

function RoomPageInner() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const roomId = params.roomId as string;
  const soloMode = searchParams.get("mode") === "solo";

  const [userName, setUserName] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Get user name from session storage
    const storedName = sessionStorage.getItem("userName");

    if (!storedName) {
      if (soloMode) {
        // 솔로(대면) 모드는 이름 없이도 바로 시작
        setUserName("나");
        setIsLoading(false);
        return;
      }
      // Redirect to home if no user name
      router.push("/");
      return;
    }

    setUserName(storedName);
    setIsLoading(false);
  }, [router, soloMode]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4" />
          <p className="text-gray-600">로딩 중...</p>
        </div>
      </div>
    );
  }

  if (!userName) {
    return null;
  }

  return <TranslatorRoom roomId={roomId} userName={userName} soloMode={soloMode} />;
}

export default function RoomPage() {
  return (
    <Suspense fallback={null}>
      <RoomPageInner />
    </Suspense>
  );
}
