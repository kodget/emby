import type { Metadata, Viewport } from "next";
import { Inter, Sora, Geist_Mono } from "next/font/google";
import { ReduxProvider } from "@/store/redux-provider";
import { GoogleAuthProvider } from "@/components/auth/google-auth-provider";
import { PwaRegister } from "@/components/pwa/pwa-register";
import { AppInitializer } from "@/components/app/app-initializer";
import { NotificationProvider } from "@/components/app/notification-provider";
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
  icons: {
    icon: "/icon.svg",
    apple: "/apple-icon.png",
  },
  manifest: "/manifest.json",
};

// Next requires themeColor on the viewport export, not metadata. It also carries the
// viewport-fit setting the app shell's safe-area padding depends on.
export const viewport: Viewport = {
  themeColor: "#6D4AFF",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
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
        <script src="https://accounts.google.com/gsi/client" async defer></script>
      </head>
      <body className="font-sans antialiased">
        <ReduxProvider>
          <AppInitializer>
            <GoogleAuthProvider>
              <NotificationProvider>
                {children}
                <PwaRegister />
                <Toaster />
              </NotificationProvider>
            </GoogleAuthProvider>
          </AppInitializer>
        </ReduxProvider>
      </body>
    </html>
  );
}
