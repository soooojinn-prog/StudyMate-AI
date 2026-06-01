import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "StudyMate AI",
  description: "Multi-agent learning system for 정보처리기사 실기",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="font-body bg-bg text-ink antialiased">{children}</body>
    </html>
  );
}
