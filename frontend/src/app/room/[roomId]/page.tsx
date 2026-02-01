"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { TranslatorRoom } from "@/components/TranslatorRoom";

export default function RoomPage() {
  const params = useParams();
  const router = useRouter();
  const roomId = params.roomId as string;

  const [userName, setUserName] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Get user name from session storage
    const storedName = sessionStorage.getItem("userName");

    if (!storedName) {
      // Redirect to home if no user name
      router.push("/");
      return;
    }

    setUserName(storedName);
    setIsLoading(false);
  }, [router]);

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

  return <TranslatorRoom roomId={roomId} userName={userName} />;
}
