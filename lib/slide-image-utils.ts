/**
 * Slide Image Utilities
 *
 * Convert slide image URLs to base64 for the Gemini Vision API.
 * The AI CANNOT see images unless we convert them to base64 and include them
 * in every API call.
 */

const imageCache = new Map<string, { value: string; expires: number }>();
let cacheSession: string | null = null;
const currentSession = () => typeof window === "undefined" ? null : sessionStorage.getItem("token");

/**
 * Download a slide image and convert to base64.
 * Returns just the base64 data (no "data:image/..." prefix).
 * Caches results so each URL is only fetched once.
 */
export async function imageUrlToBase64(imageUrl: string): Promise<string> {
  if (!imageUrl) return "";
  const session = currentSession();
  if (session !== cacheSession) { imageCache.clear(); cacheSession = session; }
  if (!session) return "";

  // Return cached version if available
  const cached = imageCache.get(imageUrl);
  if (cached && cached.expires > Date.now()) return cached.value;
  imageCache.delete(imageUrl);

  try {
    const response = await fetch(imageUrl);
    if (!response.ok) {
      console.warn("Could not load the slide image.");
      return "";
    }

    const blob = await response.blob();

    return new Promise<string>((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        if (session !== currentSession()) { resolve(""); return; }
        const dataUrl = reader.result as string;
        // Strip the "data:image/jpeg;base64," prefix — only raw data needed
        const base64Data = dataUrl.split(",")[1] ?? "";
        if (imageCache.size >= 12) imageCache.delete(imageCache.keys().next().value!);
        imageCache.set(imageUrl, { value: base64Data, expires: Date.now() + 5 * 60 * 1000 });
        resolve(base64Data);
      };
      reader.onerror = () => resolve("");
      reader.readAsDataURL(blob);
    });
  } catch (error) {
    console.warn("Could not convert the slide image.");
    return "";
  }
}

/**
 * Preload the next N slide images in the background.
 * Call this after slide index changes to ensure fast switching.
 */
export async function prefetchSlideImages(
  imageUrls: string[],
  fromIndex: number,
  count = 2,
) {
  const targets = imageUrls.slice(fromIndex + 1, fromIndex + 1 + count);
  await Promise.all(targets.map((url) => imageUrlToBase64(url)));
}
