import type { Metadata } from "next";
import { Inter, Sora, Geist_Mono } from "next/font/google";
import { ReduxProvider } from "@/store/redux-provider";
import { GoogleAuthProvider } from "@/components/auth/google-auth-provider";
import { PwaRegister } from "@/components/pwa/pwa-register";
import { AppInitializer } from "@/components/app/app-initializer";
import { Toaster } from "@/components/ui/toaster";

import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});
const sora = Sora({
  subsets: ["latin"],
  variable: "--font-sora",
  display: "swap",
  weight: ["500", "600", "700"],
});
const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Emby, the study OS for medical students",
  description:
    "Course slides, an AI tutor that reads alongside you, past questions, timed quizzes, flashcards, and steeplechase practice. All in one place, made for BMS students.",
  generator: "v0.app",
  themeColor: "#0b0e16",
  icons: {
    icon: "/icon.svg",
    apple: "/apple-icon.png",
  },
  manifest: "/manifest.json",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${sora.variable} ${geistMono.variable} bg-background`}
    >
      <head>
        {/* Display: Clash Display · Body: Satoshi — served from Fontshare */}
        <link rel="preconnect" href="https://api.fontshare.com" crossOrigin="anonymous" />
        <link
          href="https://api.fontshare.com/v2/css?f[]=clash-display@500,600,700&f[]=satoshi@400,500,700,900&display=swap"
          rel="stylesheet"
        />
        <script src="https://accounts.google.com/gsi/client" async defer></script>
      </head>
      <body className="font-sans antialiased">
        <ReduxProvider>
          <AppInitializer>
            <GoogleAuthProvider>
              {children}
              <PwaRegister />
              <Toaster />
            </GoogleAuthProvider>
          </AppInitializer>
        </ReduxProvider>
      </body>
    </html>
  );
}
