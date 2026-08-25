// lib/curriculum.ts
import api from "./api";
// Canonical modular curriculum structure.
// This is the single source of truth used by the upload modal,
// quiz generator, steeplechase, and course pages.

export type SubBlockId = string; // e.g. "anat-b1-gross"
export type BlockId = string; // e.g. "anat-b1"
export type SubjectId =
  | "anatomy"
  | "physiology"
  | "medical-biochemistry"
  | string;

export type TopicId = string; // e.g. "upper-limb"

export type Topic = {
  id: TopicId;
  title: string;
};

export type SubBlock = {
  id: SubBlockId;
  title: string;
  shortTitle: string;
  topics: Topic[];
};

export type Block = {
  id: BlockId;
  title: string; // e.g. "Block 1"
  subjectId: SubjectId;
  subBlocks: SubBlock[];
  topics: Topic[]; // Topics that belong directly to block (no sub-block)
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
        const subBlocksResponse = await api.get(`/api/sub-blocks/?block=${block.id}`);
        const subBlocks = subBlocksResponse.data;

        // Fetch topics that belong directly to the block (no sub-block)
        let blockTopics: any[] = [];
        try {
          const blockTopicsResponse = await api.get(`/api/topics/?block=${block.id}`);
          blockTopics = blockTopicsResponse.data;
        } catch (e) {
          console.warn(`Failed to fetch topics for block ${block.id}`, e);
        }

        const blockSubBlocks: SubBlock[] = [];
        for (const subBlock of subBlocks) {
          // Fetch topics for this sub-block
          let subBlockTopics: any[] = [];
          try {
            const subBlockTopicsResponse = await api.get(`/api/topics/?sub_block=${subBlock.id}`);
            subBlockTopics = subBlockTopicsResponse.data;
          } catch (e) {
            console.warn(`Failed to fetch topics for sub-block ${subBlock.id}`, e);
          }

          blockSubBlocks.push({
            id: subBlock.id,
            title: subBlock.name,
            shortTitle: subBlock.name,
            topics: subBlockTopics.map((s: any) => ({
              id: s.id,
              title: s.name,
            })),
          });
        }

        subjectData.blocks.push({
          id: block.id,
          title: block.name,
          subjectId: subject.id as SubjectId,
          subBlocks: blockSubBlocks,
          topics: blockTopics.map((s: any) => ({
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

export function getSubBlock(
  subBlockId: SubBlockId,
): { subject: Subject; block: Block; subBlock: SubBlock } | undefined {
  for (const s of curriculum) {
    for (const b of s.blocks) {
      const t = b.subBlocks.find((t) => t.id === subBlockId);
      if (t) return { subject: s, block: b, subBlock: t };
    }
  }
}

export function breadcrumb(courseId: string): string {
  const subBlockData = getSubBlock(courseId);
  if (subBlockData) {
    return `${subBlockData.subject.title} · ${subBlockData.block.title} · ${subBlockData.subBlock.title}`;
  }

  const block = getBlock(courseId);
  if (block) {
    const subject = getSubject(block.subjectId);
    const subjectTitle = subject?.title ?? block.subjectId;
    return `${subjectTitle} · ${block.title}`;
  }

  return courseId;
}
