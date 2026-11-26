import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Adaptive Knowledge Tracing | Student Portal",
  description: "Multi-Response Student Behaviour Modeling & Difficulty Scaffolding with PyTorch Behavior-AKT",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0B1120] text-slate-100 antialiased">
        {children}
      </body>
    </html>
  );
}

