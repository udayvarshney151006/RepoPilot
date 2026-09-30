import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: {
    default: "RepoPilot · Codebase intelligence",
    template: "%s · RepoPilot",
  },
  description:
    "Understand, navigate, and debug your codebase with grounded AI, source citations, and reviewable changes.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      data-theme="dark"
      data-scroll-behavior="smooth"
      suppressHydrationWarning
    >
      <body>{children}</body>
    </html>
  );
}
