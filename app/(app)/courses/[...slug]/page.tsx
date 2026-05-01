"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, BookOpen, FileText, Loader2, Play } from "lucide-react";
import Link from "next/link";
import { curriculumApi } from "@/lib/api";
import type { Slide, Material } from "@/lib/api";

export default function CourseMaterialsPage() {
  const params = useParams();
  const router = useRouter();
  const [slides, setSlides] = useState<Slide[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);

  // Extract IDs from params
  const pathSegments = params.slug as string[];
  const subjectId = pathSegments[0];
  const blockId = pathSegments[1];
  const topicId = pathSegments[2];
  const sectionId = pathSegments[3] || pathSegments[2];

  useEffect(() => {
    loadMaterials();
  }, []);

  const loadMaterials = async () => {
    try {
      const filters: any = { subject: subjectId, block: blockId };
      
      if (pathSegments.length === 4) {
        // Has topic and section
        filters.topic = topicId;
        filters.section = sectionId;
      } else if (pathSegments.length === 3) {
        // Has section only
        filters.section = sectionId;
      }
      // If pathSegments.length === 2, only filter by subject and block

      console.log('Loading materials with filters:', filters);
      console.log('Path segments:', pathSegments);
      console.log('Subject:', subjectId, 'Block:', blockId, 'Section:', sectionId);

      const [slidesData, materialsData] = await Promise.all([
        curriculumApi.getSlides(filters).catch((err) => {
          console.error('Failed to load slides:', err);
          return [];
        }),
        curriculumApi.getMaterials(filters).catch((err) => {
          console.error('Failed to load materials:', err);
          return [];
        }),
      ]);

      console.log('Loaded slides:', slidesData);
      console.log('Loaded materials:', materialsData);

      setSlides(slidesData);
      setMaterials(materialsData);
    } catch (error) {
      console.error("Failed to load materials:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const hasContent = slides.length > 0 || materials.length > 0;

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      <button
        onClick={() => router.back()}
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6 transition-colors"
      >
        <ArrowLeft className="size-4" />
        Back to courses
      </button>

      <div className="mb-8">
        <h1 className="font-serif text-4xl font-bold mb-2">Course Materials</h1>
        <p className="text-muted-foreground">
          {hasContent
            ? "Click on any material to start reading"
            : "No materials uploaded yet for this section"}
        </p>
      </div>

      {!hasContent ? (
        <div className="text-center py-12 rounded-2xl border border-border bg-card">
          <BookOpen className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
          <h3 className="font-serif text-xl mb-2">No materials available</h3>
          <p className="text-sm text-muted-foreground mb-6">
            Materials will appear here once they're uploaded by class heads
          </p>
          <Link
            href="/courses"
            className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
          >
            <ArrowLeft className="size-4" />
            Browse other courses
          </Link>
        </div>
      ) : (
        <div className="space-y-8">
          {slides.length > 0 && (
            <section>
              <h2 className="font-serif text-2xl font-semibold mb-4 flex items-center gap-2">
                <FileText className="size-6 text-primary" />
                Slides for Reading
              </h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {slides.map((slide) => (
                  <Link
                    key={slide.id}
                    href={`/read/${subjectId}/${slide.id}`}
                    className="group rounded-2xl border border-border bg-card p-5 hover:border-primary/50 hover:shadow-lg transition-all"
                  >
                    <div className="flex items-start gap-3 mb-3">
                      <div className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                        <FileText className="size-6" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="font-semibold leading-tight group-hover:text-primary transition-colors line-clamp-2">
                          {slide.title}
                        </h3>
                        <p className="text-xs text-muted-foreground mt-1">
                          {slide.file_type.toUpperCase()} • {slide.page_count} pages
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center justify-between text-xs text-muted-foreground pt-3 border-t border-border">
                      <span>By {slide.uploaded_by_name}</span>
                      <span className="text-primary group-hover:translate-x-1 transition-transform">
                        Read →
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {materials.length > 0 && (
            <section>
              <h2 className="font-serif text-2xl font-semibold mb-4 flex items-center gap-2">
                <BookOpen className="size-6 text-primary" />
                Additional Materials
              </h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {materials.map((material) => (
                  <a
                    key={material.id}
                    href={material.file_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group rounded-2xl border border-border bg-card p-5 hover:border-primary/50 hover:shadow-lg transition-all"
                  >
                    <div className="flex items-start gap-3 mb-3">
                      <div className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                        {material.material_type === "video" ? (
                          <Play className="size-6" />
                        ) : (
                          <FileText className="size-6" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="font-semibold leading-tight group-hover:text-primary transition-colors line-clamp-2">
                          {material.title}
                        </h3>
                        <p className="text-xs text-muted-foreground mt-1">
                          {material.material_type.toUpperCase()}
                        </p>
                      </div>
                    </div>
                    {material.description && (
                      <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
                        {material.description}
                      </p>
                    )}
                    <div className="flex items-center justify-between text-xs text-muted-foreground pt-3 border-t border-border">
                      <span>By {material.uploaded_by_name}</span>
                      <span className="text-primary group-hover:translate-x-1 transition-transform">
                        Open →
                      </span>
                    </div>
                  </a>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
