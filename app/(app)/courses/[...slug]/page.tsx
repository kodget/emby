"use client";

import { WorkspaceHeader, WorkspaceEmpty } from "@/components/ui/workspace-header";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, BookOpen, FileText, Loader2, Play } from "lucide-react";
import { isAxiosError } from "axios";
import Link from "next/link";
import { curriculumApi } from "@/lib/api";
import type { Slide, Material, SubBlock } from "@/lib/api";
import { useContentSessionKey } from "@/store/hooks";
import { MaterialFileLink } from "@/components/app/material-file-link";

export default function CourseMaterialsPage() {
  const params = useParams();
  const sessionKey = useContentSessionKey();
  const router = useRouter();
  const [slides, setSlides] = useState<Slide[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [pageTitle, setPageTitle] = useState("Course Materials");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  const pathSegments = params.slug as string[];
  const subjectId = pathSegments[0];
  const blockId = pathSegments[1];
  const topicId = pathSegments.length === 4 ? pathSegments[2] : undefined;
  const sectionId = pathSegments.length === 4 ? pathSegments[3] : undefined;
  const childId = pathSegments.length === 3 ? pathSegments[2] : undefined;

  useEffect(() => {
    let active = true;
    const session = sessionStorage.getItem("user");
    const current = () => active && session === sessionStorage.getItem("user");
    async function loadMaterials() {
      setLoading(true);
      setError(""); setSlides([]); setMaterials([]);
      try {
        let filters: { subject: string; block: string; sub_block?: string; topic?: string } = {
          subject: subjectId,
          block: blockId,
        };
        let node: { name: string };

        if (sectionId && topicId) {
          filters = { ...filters, sub_block: topicId, topic: sectionId };
          node = await curriculumApi.getTopic(sectionId);
        } else if (childId) {
          let subBlock: SubBlock | undefined;
          try {
            subBlock = await curriculumApi.getSubBlock(childId);
          } catch (error: any) {
            if (error?.response?.status !== 404) throw error;
          }
          if (subBlock?.block === blockId) {
            filters = { ...filters, sub_block: childId };
            node = subBlock;
          } else {
            const topic = await curriculumApi.getTopic(childId);
            if (topic.block !== blockId) throw new Error("Course section does not belong to this module.");
            filters = { ...filters, topic: childId };
            node = topic;
          }
        } else {
          node = await curriculumApi.getBlock(blockId);
        }

        const [nextSlides, nextMaterials] = await Promise.all([
          curriculumApi.getSlides(filters),
          curriculumApi.getMaterials(filters),
        ]);
        if (current()) {
          setSlides(nextSlides);
          setMaterials(nextMaterials);
          setPageTitle(node.name);
        }
      } catch (error) {
        if (current()) {
          setError(isAxiosError(error) && error.response
            ? `Could not load these materials (HTTP ${error.response.status}). Please try again.`
            : "Could not load these materials. Please try again.");
        }
      } finally {
        if (current()) setLoading(false);
      }
    }
    loadMaterials();
    return () => { active = false; };
  }, [subjectId, blockId, topicId, sectionId, childId, sessionKey, attempt]);

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

      <WorkspaceHeader className="mb-6" eyebrow="Follow the subject" title={pageTitle} description={error ? "Materials are temporarily unavailable." : hasContent ? "Open a material, follow a concept, and start making connections." : "Your class materials will appear here once they’re shared."} />

      {error ? (
        <div role="alert" className="rounded-xl border border-destructive p-4">
          <p>{error}</p>
          <button
            className="mt-3 min-h-11 cursor-pointer underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() => setAttempt((value) => value + 1)}
            disabled={loading}
          >
            Try again
          </button>
        </div>
      ) : !hasContent ? (
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
                          {slide.file_type.toUpperCase()} • {slide.page_count}{" "}
                          pages
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
                  <MaterialFileLink
                    key={material.id}
                    id={material.id}
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
                  </MaterialFileLink>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
