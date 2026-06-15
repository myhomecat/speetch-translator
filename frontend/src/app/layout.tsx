import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ConfigProvider } from "@/lib/config-context";

// 런타임에 서버가 env를 읽도록 동적 렌더 강제 (빌드 프리렌더 방지)
export const dynamic = "force-dynamic";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "음성 번역기 - 한국어/일본어 실시간 번역",
  description: "실시간 한국어-일본어 동시 음성 번역 채팅방",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // 런타임 env (docker run -e WS_URL=...) — NEXT_PUBLIC 아님 = 서버가 런타임에 읽음
  const config = {
    WS_URL: process.env.WS_URL || "ws://localhost:8000",
    API_URL: process.env.API_URL || "http://localhost:8000",
  };
  return (
    <html lang="ko">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <ConfigProvider value={config}>{children}</ConfigProvider>
      </body>
    </html>
  );
}
