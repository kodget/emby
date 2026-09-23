// Backend-backed slide helpers. No sample content is kept in the browser bundle.
import { curriculumApi } from "./api";
import type { TopicId, BlockId } from "./curriculum";

export type SlideId = string;
export type SlideContent = { pageNumber: number; imageUrl: string; text?: string };
export type Slide = {
  id: SlideId;
  title: string;
  topicId?: TopicId;
  blockId?: BlockId;
  pages: number;
  uploadedBy: string;
  uploadedAt: string;
  fileUrl?: string;
  thumbnailUrl?: string;
  content?: SlideContent[];
};

function mapApiSlide(apiSlide: any): Slide {
  return {
    id: String(apiSlide.id ?? apiSlide.slug ?? ""),
    title: apiSlide.title ?? "",
    topicId: apiSlide.topic ?? apiSlide.sub_block ?? undefined,
    blockId: apiSlide.block ?? undefined,
    pages: apiSlide.page_count ?? apiSlide.pages ?? 0,
    uploadedBy: apiSlide.uploaded_by_name ?? apiSlide.uploaded_by ?? "",
    uploadedAt: apiSlide.created_at ?? "",
    fileUrl: apiSlide.file_url ?? undefined,
    thumbnailUrl: apiSlide.thumbnail_url ?? undefined,
  };
}

export async function getSlidesByTopic(topicId: TopicId): Promise<Slide[]> {
  try {
    return (await curriculumApi.getSlides({ topic: topicId })).map(mapApiSlide);
  } catch (error) {
    console.warn(`Failed to fetch slides for topic ${topicId}`, error);
    return [];
  }
}

export async function getSlidesByBlock(blockId: BlockId): Promise<Slide[]> {
  try {
    return (await curriculumApi.getSlides({ block: blockId })).map(mapApiSlide);
  } catch (error) {
    console.warn(`Failed to fetch slides for block ${blockId}`, error);
    return [];
  }
}

export async function getSlideById(slideId: SlideId): Promise<Slide | undefined> {
  try {
    return mapApiSlide(await curriculumApi.getSlide(slideId));
  } catch (error) {
    console.warn(`Failed to fetch slide ${slideId}`, error);
    return undefined;
  }
}

export async function getSlidesForCourse(courseId: string): Promise<Slide[]> {
  const topicSlides = await getSlidesByTopic(courseId);
  return topicSlides.length > 0 ? topicSlides : getSlidesByBlock(courseId);
}
