import { api } from "./api";

/** Route AI requests through the authenticated backend; provider credentials never
 * belong in the browser bundle. */
export async function fetchGemini(prompt: string) {
  const response = await api.post("/api/ai/chat/", { message: prompt });
  return response.data;
}
