"use client"

import { GoogleOAuthProvider } from "@react-oauth/google"

export function GoogleAuthProvider({ children }: { children: React.ReactNode }) {
  // Get Google Client ID from environment variable
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || ""

  if (!clientId) {
    console.warn("Google Client ID not found. Please set NEXT_PUBLIC_GOOGLE_CLIENT_ID in .env.local")
    return <>{children}</>
  }

  return (
    <GoogleOAuthProvider clientId={clientId}>
      {children}
    </GoogleOAuthProvider>
  )
}
