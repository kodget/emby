"use client";

import { useUserInit } from "@/hooks/use-user-init";
import { ReactNode } from "react";

export function AppInitializer({ children }: { children: ReactNode }) {
  useUserInit();
  return <>{children}</>;
}
