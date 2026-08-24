// lib/curriculum.ts
import api from "./api";
// Canonical modular curriculum structure.
// This is the single source of truth used by the upload modal,
// quiz generator, steeplechase, and course pages.

export type TopicId = string; // e.g. "anat-b1-gross"
export type BlockId = string; // e.g. "anat-b1"
export type SubjectId =
  | "anatomy"
  | "physiology"
  | "medical-biochemistry"
  | string;

export type SectionId = string; // e.g. "upper-limb"

export type Section = {
  id: SectionId;
  title: string;
};

export type Topic = {
  id: TopicId;
  title: string;
  shortTitle: string;
  sections: Section[];
};

export type Block = {
  id: BlockId;
  title: string; // e.g. "Block 1"
  subjectId: SubjectId;
  topics: Topic[];
  sections: Section[]; // Sections that belong directly to block (no topic)
};

export type Subject = {
  id: SubjectId;
  title: string;
  color: string;
  icon: string; // lucide icon name
  blocks: Block[];
};

// NOTE: This will be replaced with dynamic API fetching
// For now, keeping minimal structure for backward compatibility
export const curriculum: Subject[] = [];

// Dynamic curriculum loader
let cachedCurriculum: Subject[] | null = null;

export async function loadCurriculum(): Promise<Subject[]> {
  if (cachedCurriculum) return cachedCurriculum;

  try {
    const response = await api.get(`/api/subjects/`);
    const subjects = response.data;

    const curriculum: Subject[] = [];

    for (const subject of subjects) {
      const blocksResponse = await api.get(`/api/blocks/?subject=${subject.id}`);
      const blocks = blocksResponse.data;

      const subjectData: Subject = {
        id: subject.id as SubjectId,
        title: subject.name,
        color:
          subject.id === "anatomy"
            ? "#0d6b5e"
            : subject.id === "physiology"
              ? "#b94a3b"
              : subject.id === "medical-biochemistry"
                ? "#6b7d3a"
                : "#0d6b5e",
        icon:
          subject.id === "anatomy"
            ? "Bone"
            : subject.id === "physiology"
              ? "HeartPulse"
              : subject.id === "medical-biochemistry"
                ? "FlaskConical"
                : "Bone",
        blocks: [],
      };

      for (const block of blocks) {
        const topicsResponse = await api.get(`/api/sub-blocks/?block=${block.id}`);
        const topics = topicsResponse.data;

        // Fetch sections (topics in new schema) that belong directly to the block (no topic)
        let blockSections: any[] = [];
        try {
          const blockSectionsResponse = await api.get(`/api/topics/?block=${block.id}`);
          blockSections = blockSectionsResponse.data;
        } catch (e) {
          console.warn(`Failed to fetch sections for block ${block.id}`, e);
        }

        const blockTopics: Topic[] = [];
        for (const topic of topics) {
          // Fetch sections (topics in new schema) for this topic
          let topicSections: any[] = [];
          try {
            const topicSectionsResponse = await api.get(`/api/topics/?sub_block=${topic.id}`);
            topicSections = topicSectionsResponse.data;
          } catch (e) {
            console.warn(`Failed to fetch sections for topic ${topic.id}`, e);
          }

          blockTopics.push({
            id: topic.id,
            title: topic.name,
            shortTitle: topic.name,
            sections: topicSections.map((s: any) => ({
              id: s.id,
              title: s.name,
            })),
          });
        }

        subjectData.blocks.push({
          id: block.id,
          title: block.name,
          subjectId: subject.id as SubjectId,
          topics: blockTopics,
          sections: blockSections.map((s: any) => ({
            id: s.id,
            title: s.name,
          })),
        });
      }

      curriculum.push(subjectData);
    }

    cachedCurriculum = curriculum;
    return curriculum;
  } catch (error) {
    console.error("Failed to load curriculum:", error);
    // Don't swallow the error - let the caller handle it
    throw error;
  }
}

// ── Lookup helpers ──────────────────────────────────────────

export function getSubject(id: SubjectId): Subject | undefined {
  return curriculum.find((s) => s.id === id);
}

export function getBlock(blockId: BlockId): Block | undefined {
  for (const s of curriculum) {
    const b = s.blocks.find((b) => b.id === blockId);
    if (b) return b;
  }
}

export function getTopic(
  topicId: TopicId,
): { subject: Subject; block: Block; topic: Topic } | undefined {
  for (const s of curriculum) {
    for (const b of s.blocks) {
      const t = b.topics.find((t) => t.id === topicId);
      if (t) return { subject: s, block: b, topic: t };
    }
  }
}

export function breadcrumb(courseId: string): string {
  const topic = getTopic(courseId);
  if (topic) {
    return `${topic.subject.title} · ${topic.block.title} · ${topic.topic.title}`;
  }

  const block = getBlock(courseId);
  if (block) {
    const subject = getSubject(block.subjectId);
    const subjectTitle = subject?.title ?? block.subjectId;
    return `${subjectTitle} · ${block.title}`;
  }

  return courseId;
}
