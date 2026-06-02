/**
 * Slide Image Utilities
 *
 * Convert slide image URLs to base64 for the Gemini Vision API.
 * The AI CANNOT see images unless we convert them to base64 and include them
 * in every API call.
 */

const imageCache = new Map<string, string>();

/**
 * Download a slide image and convert to base64.
 * Returns just the base64 data (no "data:image/..." prefix).
 * Caches results so each URL is only fetched once.
 */
export async function imageUrlToBase64(imageUrl: string): Promise<string> {
  if (!imageUrl) return "";

  // Return cached version if available
  if (imageCache.has(imageUrl)) {
    return imageCache.get(imageUrl)!;
  }

  try {
    const response = await fetch(imageUrl);
    if (!response.ok) {
      console.warn(`Failed to fetch image for base64 conversion: ${imageUrl}`);
      return "";
    }

    const blob = await response.blob();

    return new Promise<string>((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const dataUrl = reader.result as string;
        // Strip the "data:image/jpeg;base64," prefix — only raw data needed
        const base64Data = dataUrl.split(",")[1] ?? "";
        imageCache.set(imageUrl, base64Data);
        resolve(base64Data);
      };
      reader.onerror = () => resolve("");
      reader.readAsDataURL(blob);
    });
  } catch (error) {
    console.warn("imageUrlToBase64 failed:", error);
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
