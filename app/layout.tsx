import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Omium | Autonomous Security Orchestration",
  description:
    "Omium Mission Control — AI-driven autonomous red-team, vulnerability detection, and remediation engine.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap"
        />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200"
        />
      </head>
      <body className="bg-surface-deep text-on-surface overflow-hidden h-screen flex">
        {children}
      </body>
    </html>
  );
}
