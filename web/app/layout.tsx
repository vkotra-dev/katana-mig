import type { ReactNode } from "react";
import "./globals.css";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html className="light" lang="en">
      <body>{children}</body>
    </html>
  );
}

