"use client"

import { GoogleOAuthProvider } from "@react-oauth/google"

export function GoogleAuthProvider({ children }: { children: React.ReactNode }) {
  // Get Google Client ID from environment variable
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || ""

  if (!clientId) {
    console.warn("Google Client ID not found. Google sign-in will remain unavailable until configured.")
  }

  return (
    <GoogleOAuthProvider clientId={clientId || "not-configured"}>
      {children}
    </GoogleOAuthProvider>
  )
}
