// Root layout: fonts, metadata, and the theme script that runs before paint (no flash).

import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";

import { THEME_INIT_SCRIPT } from "@/lib/theme";

const geist = Geist({
  variable: "--font-geist",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "ProjectFlow",
  description: "Plan projects with dependencies, critical path and workload.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // The theme script adds the "dark" class before hydration.
    <html lang="en" className={`${geist.variable} h-full antialiased`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
