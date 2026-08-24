"use client";

/**
 * Class Curriculum Management Page
 *
 * Class heads use this page to structure:
 *   Subject (Level 1) → Block (Level 2) → Sub-block (Level 3, optional) → Topic (Level 4, gotten from slide upload) → Slides (Level 5)
 *
 * Levels 1, 2, and 3 are manually managed. Level 4 (Topics) are created/populated from slide uploads
 * and can be renamed or deleted from here.
 */

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  Edit2,
  Loader2,
  Plus,
  Trash2,
  X,
  AlertCircle,
  Layers,
  FileText,
  Film,
  File,
  Image,
  FolderOpen,
} from "lucide-react";
import AuthGuard from "@/components/auth/auth-guard";
import { isClassHead } from "@/lib/guards";
import { curriculumApi } from "@/lib/api";
import api from "@/lib/api";
import type { Subject, Block, SubBlock, Topic, Slide } from "@/lib/api";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

type FormMode = "add" | "edit";
type ItemType = "subject" | "block" | "sub-block" | "topic";

interface FormState {
  open: boolean;
  mode: FormMode;
  type: ItemType;
  name: string;
  description: string;
  parentSubjectId?: string;
  parentBlockId?: string;
  editId?: string;
}

interface DeleteState {
  type: ItemType | "slide";
  id: string;
  name: string;
}

interface GroupedTopic {
  id: string;
  name: string;
  slides: Slide[];
}

const CLOSED_FORM: FormState = {
  open: false,
  mode: "add",
  type: "subject",
  name: "",
  description: "",
};

// ─────────────────────────────────────────────────────────────────────────────
// API helpers
// ─────────────────────────────────────────────────────────────────────────────

async function apiPost(path: string, body: object) {
  const res = await api.post(`/api${path}`, body);
  return res.data;
}

async function apiPatch(path: string, body: object) {
  const res = await api.patch(`/api${path}`, body);
  return res.data;
}

async function apiDelete(path: string) {
  await api.delete(`/api${path}`);
}

function slideIcon(fileType?: string) {
  if (!fileType) return <File className="size-3.5" />;
  if (fileType === "pdf") return <FileText className="size-3.5 text-rose-500" />;
  if (fileType === "pptx" || fileType === "ppt") return <Film className="size-3.5 text-orange-500" />;
  if (fileType === "docx" || fileType === "doc") return <FileText className="size-3.5 text-blue-500" />;
  return <Image className="size-3.5 text-purple-500" />;
}

// Extract unique topics from a list of slides
function getUniqueTopics(slides: Slide[]): GroupedTopic[] {
  const topicsMap: Record<string, GroupedTopic> = {};
  slides.forEach((slide) => {
    if (slide.topic) {
      if (!topicsMap[slide.topic]) {
        topicsMap[slide.topic] = {
          id: slide.topic,
          name: slide.topic_name || "Untitled Topic",
          slides: [],
        };
      }
      topicsMap[slide.topic].slides.push(slide);
    }
  });
  return Object.values(topicsMap);
}

// ─────────────────────────────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────────────────────────────

export default function CurriculumManagementPage() {
  const router = useRouter();
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [blocksMap, setBlocksMap] = useState<Record<string, Block[]>>({});
  const [subBlocksMap, setSubBlocksMap] = useState<Record<string, SubBlock[]>>({});
  
  // Slides keyed by block ID
  const [blockSlidesMap, setBlockSlidesMap] = useState<Record<string, Slide[]>>({});
  const [loadingSlidesForBlock, setLoadingSlidesForBlock] = useState<Set<string>>(new Set());

  const [expandedSubjects, setExpandedSubjects] = useState<Set<string>>(new Set());
  const [expandedBlocks, setExpandedBlocks] = useState<Set<string>>(new Set());
  const [expandedSubBlocks, setExpandedSubBlocks] = useState<Set<string>>(new Set());
  const [expandedTopics, setExpandedTopics] = useState<Set<string>>(new Set());

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState<FormState>(CLOSED_FORM);
  const [deleteConfirm, setDeleteConfirm] = useState<DeleteState | null>(null);

  useEffect(() => {
    if (!isClassHead()) router.replace("/class");
  }, [router]);

  useEffect(() => { loadAll(); }, []);

  async function loadAll() {
    setLoading(true);
    setError("");
    try {
      const subs = await curriculumApi.getSubjects();
      setSubjects(subs);
      const bMap: Record<string, Block[]> = {};
      await Promise.all(subs.map(async (s) => {
        const blks = await curriculumApi.getBlocks(s.id);
        bMap[s.id] = blks;
      }));
      setBlocksMap(bMap);
      const sbMap: Record<string, SubBlock[]> = {};
      const allBlocks = Object.values(bMap).flat();
      await Promise.all(allBlocks.map(async (b) => {
        const subBlks = await curriculumApi.getSubBlocks(b.id);
        sbMap[b.id] = subBlks;
      }));
      setSubBlocksMap(sbMap);
    } catch (e: any) {
      setError("Failed to load curriculum. " + e.message);
    } finally {
      setLoading(false);
    }
  }

  // Load slides for a block
  const loadSlidesForBlock = useCallback(async (blockId: string) => {
    if (blockSlidesMap[blockId] !== undefined || loadingSlidesForBlock.has(blockId)) return;
    setLoadingSlidesForBlock((prev) => new Set(prev).add(blockId));
    try {
      const res = await api.get(`/api/slides/?block=${blockId}`);
      const slides: Slide[] = Array.isArray(res.data)
        ? res.data
        : (res.data?.results ?? []);
      setBlockSlidesMap((prev) => ({ ...prev, [blockId]: slides }));
    } catch {
      setBlockSlidesMap((prev) => ({ ...prev, [blockId]: [] }));
    } finally {
      setLoadingSlidesForBlock((prev) => {
        const s = new Set(prev);
        s.delete(blockId);
        return s;
      });
    }
  }, [blockSlidesMap, loadingSlidesForBlock]);

  function toggleBlock(blockId: string) {
    setExpandedBlocks((prev) => {
      const s = new Set(prev);
      if (s.has(blockId)) {
        s.delete(blockId);
      } else {
        s.add(blockId);
        loadSlidesForBlock(blockId);
      }
      return s;
    });
  }

  // ── Form helpers ───────────────────────────────────────────────────────────

  function openAddSubject() {
    setForm({ open: true, mode: "add", type: "subject", name: "", description: "" });
  }

  function openAddBlock(subjectId: string) {
    setForm({ open: true, mode: "add", type: "block", name: "", description: "", parentSubjectId: subjectId });
    setExpandedSubjects((prev) => new Set(prev).add(subjectId));
  }

  // Under a Block, we can add a Sub-block (DB Topic)
  function openAddSubBlock(blockId: string, subjectId: string) {
    setForm({ open: true, mode: "add", type: "sub-block", name: "", description: "", parentBlockId: blockId, parentSubjectId: subjectId });
    setExpandedBlocks((prev) => new Set(prev).add(blockId));
  }

  function openEdit(type: ItemType, id: string, name: string, description: string, parentSubjectId?: string, parentBlockId?: string) {
    setForm({ open: true, mode: "edit", type, name, description, editId: id, parentSubjectId, parentBlockId });
  }

  async function handleSave() {
    if (!form.name.trim()) return;
    setSaving(true);
    setError("");
    try {
      if (form.mode === "add") {
        if (form.type === "subject") {
          const created = await apiPost("/subjects/", {
            name: form.name.trim(),
            description: form.description.trim(),
            order: subjects.length,
          });
          setSubjects((prev) => [...prev, created]);
          setBlocksMap((prev) => ({ ...prev, [created.id]: [] }));
        } else if (form.type === "block" && form.parentSubjectId) {
          const created = await apiPost("/blocks/", {
            name: form.name.trim(),
            description: form.description.trim(),
            subject: form.parentSubjectId,
            order: (blocksMap[form.parentSubjectId] || []).length,
          });
          setBlocksMap((prev) => ({
            ...prev,
            [form.parentSubjectId!]: [...(prev[form.parentSubjectId!] || []), created],
          }));
          setSubBlocksMap((prev) => ({ ...prev, [created.id]: [] }));
        } else if (form.type === "sub-block" && form.parentBlockId) {
          const created = await apiPost("/sub-blocks/", {
            name: form.name.trim(),
            description: form.description.trim(),
            block: form.parentBlockId,
            order: (subBlocksMap[form.parentBlockId] || []).length,
          });
          setSubBlocksMap((prev) => ({
            ...prev,
            [form.parentBlockId!]: [...(prev[form.parentBlockId!] || []), created],
          }));
        }
      } else if (form.mode === "edit" && form.editId) {
        const patch = { name: form.name.trim(), description: form.description.trim() };
        if (form.type === "subject") {
          await apiPatch(`/subjects/${form.editId}/`, patch);
          setSubjects((prev) => prev.map((s) => s.id === form.editId ? { ...s, ...patch } : s));
        } else if (form.type === "block" && form.parentSubjectId) {
          await apiPatch(`/blocks/${form.editId}/`, patch);
          setBlocksMap((prev) => ({
            ...prev,
            [form.parentSubjectId!]: (prev[form.parentSubjectId!] || []).map((b) =>
              b.id === form.editId ? { ...b, ...patch } : b
            ),
          }));
        } else if (form.type === "sub-block" && form.parentBlockId) {
          await apiPatch(`/sub-blocks/${form.editId}/`, patch);
          setSubBlocksMap((prev) => ({
            ...prev,
            [form.parentBlockId!]: (prev[form.parentBlockId!] || []).map((t) =>
              t.id === form.editId ? { ...t, ...patch } : t
            ),
          }));
        } else if (form.type === "topic") {
          await apiPatch(`/topics/${form.editId}/`, patch);
          // Update the locally loaded slides mapping with the new topic name
          setBlockSlidesMap((prev) => {
            const next = { ...prev };
            for (const bid of Object.keys(next)) {
              next[bid] = next[bid].map((s) =>
                s.topic === form.editId ? { ...s, topic_name: form.name.trim() } : s
              );
            }
            return next;
          });
        }
      }
      setForm(CLOSED_FORM);
    } catch (e: any) {
      console.error("Status:", e.response?.status);
      console.error("Validation:", e.response?.data);
      setError(
        typeof e.response?.data === "string"
          ? e.response.data
          : JSON.stringify(e.response?.data, null, 2)
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteConfirm) return;
    const { type, id } = deleteConfirm;
    if (!id) { setDeleteConfirm(null); return; }
    setSaving(true);
    setError("");
    try {
      if (type === "subject") {
        await apiDelete(`/subjects/${id}/`);
        setSubjects((prev) => prev.filter((s) => s.id !== id));
        const nm = { ...blocksMap }; delete nm[id]; setBlocksMap(nm);
      } else if (type === "block") {
        await apiDelete(`/blocks/${id}/`);
        const nm: Record<string, Block[]> = {};
        for (const [sid, blks] of Object.entries(blocksMap)) nm[sid] = blks.filter((b) => b.id !== id);
        setBlocksMap(nm);
        const nsb = { ...subBlocksMap }; delete nsb[id]; setSubBlocksMap(nsb);
      } else if (type === "sub-block") {
        await apiDelete(`/sub-blocks/${id}/`);
        const nsb: Record<string, SubBlock[]> = {};
        for (const [bid, tops] of Object.entries(subBlocksMap)) nsb[bid] = tops.filter((t) => t.id !== id);
        setSubBlocksMap(nsb);
      } else if (type === "topic") {
        await apiDelete(`/topics/${id}/`);
        // Remove slides associated with this topic locally
        setBlockSlidesMap((prev) => {
          const next = { ...prev };
          for (const bid of Object.keys(next)) {
            next[bid] = next[bid].filter((s) => s.topic !== id);
          }
          return next;
        });
      } else if (type === "slide") {
        await apiDelete(`/slides/${id}/`);
        setBlockSlidesMap((prev) => {
          const next = { ...prev };
          for (const bid of Object.keys(next)) {
            next[bid] = next[bid].filter((s) => s.id !== id);
          }
          return next;
        });
      }
      setDeleteConfirm(null);
    } catch (e: any) {
      console.error("Status:", e.response?.status);
      console.error("Validation:", e.response?.data);
      setError(
        typeof e.response?.data === "string"
          ? e.response.data
          : JSON.stringify(e.response?.data, null, 2)
      );
    } finally {
      setSaving(false);
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <AuthGuard>
      <div className="min-h-screen bg-background">
        {/* Header */}
        <div className="sticky top-0 z-10 border-b border-border bg-background/90 px-6 py-4 backdrop-blur-md">
          <div className="mx-auto flex max-w-3xl items-center justify-between">
            <div>
              <h1 className="font-serif text-2xl font-semibold">Curriculum</h1>
              <p className="mt-0.5 text-sm text-muted-foreground">
                Manage subjects, blocks, sub-blocks, topics, and slides.
              </p>
            </div>
            <button
              onClick={openAddSubject}
              className="inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              <Plus className="size-4" /> Add Subject
            </button>
          </div>
        </div>

        <div className="mx-auto max-w-3xl px-6 py-8">
          {error && (
            <div className="mb-6 flex items-center gap-3 rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              <AlertCircle className="size-4 shrink-0" />
              <pre className="whitespace-pre-wrap font-sans text-xs">{error}</pre>
              <button onClick={() => setError("")} className="ml-auto"><X className="size-4" /></button>
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="size-8 animate-spin text-primary" />
            </div>
          ) : subjects.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed border-border py-20 text-center">
              <Layers className="size-12 text-muted-foreground" />
              <div>
                <p className="font-serif text-xl">No subjects yet</p>
                <p className="mt-1 text-sm text-muted-foreground">Start by adding a subject like &ldquo;Anatomy&rdquo;</p>
              </div>
              <button
                onClick={openAddSubject}
                className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:opacity-90"
              >
                <Plus className="size-4" /> Add first subject
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {subjects.map((subject) => {
                const blocks = blocksMap[subject.id] || [];
                const isExpanded = expandedSubjects.has(subject.id);
                return (
                  <div key={subject.id} className="rounded-2xl border border-border bg-card overflow-hidden">
                    {/* Subject row */}
                    <div className="flex items-center gap-3 px-5 py-4">
                      <button
                        onClick={() => setExpandedSubjects((prev) => {
                          const s = new Set(prev);
                          isExpanded ? s.delete(subject.id) : s.add(subject.id);
                          return s;
                        })}
                        className="flex flex-1 items-center gap-3 text-left"
                      >
                        <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                          <BookOpen className="size-4" />
                        </div>
                        <div>
                          <p className="font-semibold">{subject.name}</p>
                          <p className="text-xs text-muted-foreground">{blocks.length} block{blocks.length !== 1 ? "s" : ""}</p>
                        </div>
                        <div className="ml-auto">{isExpanded ? <ChevronDown className="size-4 text-muted-foreground" /> : <ChevronRight className="size-4 text-muted-foreground" />}</div>
                      </button>
                      <button onClick={() => openEdit("subject", subject.id, subject.name, subject.description || "")}
                        className="flex size-8 items-center justify-center rounded-full hover:bg-muted text-muted-foreground" title="Edit subject">
                        <Edit2 className="size-3.5" />
                      </button>
                      <button onClick={() => setDeleteConfirm({ type: "subject", id: subject.id, name: subject.name })}
                        className="flex size-8 items-center justify-center rounded-full hover:bg-destructive/10 text-muted-foreground hover:text-destructive" title="Delete subject">
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>

                    {/* Blocks */}
                    {isExpanded && (
                      <div className="border-t border-border bg-background/40">
                        {blocks.map((block) => {
                          const subBlocks = subBlocksMap[block.id] || [];
                          const isBlockExpanded = expandedBlocks.has(block.id);
                          const blockSlides = blockSlidesMap[block.id] || [];
                          const loadingSlides = loadingSlidesForBlock.has(block.id);

                          // Group slides that belong directly under this block
                          const directSlides = blockSlides.filter((s) => !s.sub_block);
                          const directTopics = getUniqueTopics(directSlides);
                          const directGeneralSlides = directSlides.filter((s) => !s.topic);

                          return (
                            <div key={block.id} className="border-b border-border last:border-0">
                              {/* Block row */}
                              <div className="flex items-center gap-3 px-5 py-3 pl-10">
                                <button
                                  onClick={() => toggleBlock(block.id)}
                                  className="flex flex-1 items-center gap-3 text-left"
                                >
                                  <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                                    <Layers className="size-3.5" />
                                  </div>
                                  <div>
                                    <p className="text-sm font-medium">{block.name}</p>
                                    <p className="text-xs text-muted-foreground">
                                      {subBlocks.length} sub-block{subBlocks.length !== 1 ? "s" : ""}
                                    </p>
                                  </div>
                                  <div className="ml-auto mr-2">
                                    {isBlockExpanded ? <ChevronDown className="size-3.5 text-muted-foreground" /> : <ChevronRight className="size-3.5 text-muted-foreground" />}
                                  </div>
                                </button>
                                <button onClick={() => openAddSubBlock(block.id, subject.id)}
                                  className="flex size-7 items-center justify-center rounded-full hover:bg-primary/10 text-primary" title="Add sub-block">
                                  <Plus className="size-3.5" />
                                </button>
                                <button onClick={() => openEdit("block", block.id, block.name, block.description || "", subject.id)}
                                  className="flex size-7 items-center justify-center rounded-full hover:bg-muted text-muted-foreground" title="Edit block">
                                  <Edit2 className="size-3.5" />
                                </button>
                                <button onClick={() => setDeleteConfirm({ type: "block", id: block.id, name: block.name })}
                                  className="flex size-7 items-center justify-center rounded-full hover:bg-destructive/10 text-muted-foreground hover:text-destructive" title="Delete block">
                                  <Trash2 className="size-3.5" />
                                </button>
                              </div>

                              {/* Block Content (Sub-blocks and Direct topics) */}
                              {isBlockExpanded && (
                                <div className="bg-muted/30 border-t border-border/40">
                                  {loadingSlides && blockSlides.length === 0 && (
                                    <div className="flex items-center gap-2 py-3 pl-16 text-xs text-muted-foreground">
                                      <Loader2 className="size-3 animate-spin" /> Loading contents…
                                    </div>
                                  )}

                                  {/* Render Sub-blocks (Level 3) */}
                                  {subBlocks.map((subBlock) => {
                                    const isSubBlockExpanded = expandedSubBlocks.has(subBlock.id);
                                    const subBlockSlides = blockSlides.filter((s) => s.sub_block === subBlock.id);
                                    const subBlockTopics = getUniqueTopics(subBlockSlides);
                                    const subBlockGeneralSlides = subBlockSlides.filter((s) => !s.topic);

                                    return (
                                      <div key={subBlock.id} className="border-b border-border/40 last:border-0">
                                        {/* Sub-block Row */}
                                        <div className="flex items-center gap-3 px-5 py-2.5 pl-14 bg-background/20">
                                          <button
                                            onClick={() => setExpandedSubBlocks((prev) => {
                                              const s = new Set(prev);
                                              isSubBlockExpanded ? s.delete(subBlock.id) : s.add(subBlock.id);
                                              return s;
                                            })}
                                            className="flex flex-1 items-center gap-2 text-left"
                                          >
                                            <FolderOpen className="size-3.5 text-muted-foreground/60 shrink-0" />
                                            <div>
                                              <p className="text-sm font-medium text-foreground">{subBlock.name}</p>
                                              <p className="text-[10px] text-muted-foreground">
                                                {subBlockTopics.length} topic{subBlockTopics.length !== 1 ? "s" : ""}
                                                {subBlockGeneralSlides.length > 0 ? ` · ${subBlockGeneralSlides.length} slide${subBlockGeneralSlides.length !== 1 ? "s" : ""}` : ""}
                                              </p>
                                            </div>
                                            <div className="ml-auto mr-1 text-muted-foreground">
                                              {isSubBlockExpanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
                                            </div>
                                          </button>
                                          <button onClick={() => openEdit("sub-block", subBlock.id, subBlock.name, subBlock.description || "", subject.id, block.id)}
                                            className="flex size-6 items-center justify-center rounded-full hover:bg-muted text-muted-foreground" title="Edit sub-block">
                                            <Edit2 className="size-3" />
                                          </button>
                                          <button onClick={() => setDeleteConfirm({ type: "sub-block", id: subBlock.id, name: subBlock.name })}
                                            className="flex size-6 items-center justify-center rounded-full hover:bg-destructive/10 text-muted-foreground hover:text-destructive" title="Delete sub-block">
                                            <Trash2 className="size-3" />
                                          </button>
                                        </div>

                                        {/* Topics under Sub-block */}
                                        {isSubBlockExpanded && (
                                          <div className="pl-6 bg-background/5">
                                            {/* Render Topics (Level 4, gotten from slide upload) */}
                                            {subBlockTopics.map((topic) => {
                                              const isTopicExpanded = expandedTopics.has(topic.id);
                                              return (
                                                <div key={topic.id} className="border-b border-border/30 last:border-0">
                                                  {/* Topic Row */}
                                                  <div className="flex items-center gap-3 px-5 py-2 pl-14">
                                                    <button
                                                      onClick={() => setExpandedTopics((prev) => {
                                                        const s = new Set(prev);
                                                        isTopicExpanded ? s.delete(topic.id) : s.add(topic.id);
                                                        return s;
                                                      })}
                                                      className="flex flex-1 items-center gap-2 text-left"
                                                    >
                                                      <span className="size-1.5 rounded-full bg-primary/70 shrink-0" />
                                                      <p className="text-xs text-muted-foreground font-medium">{topic.name}</p>
                                                      <span className="text-[10px] text-muted-foreground/60">
                                                        ({topic.slides.length} slide{topic.slides.length !== 1 ? "s" : ""})
                                                      </span>
                                                      <div className="ml-auto mr-1 text-muted-foreground">
                                                        {isTopicExpanded ? <ChevronDown className="size-2.5" /> : <ChevronRight className="size-2.5" />}
                                                      </div>
                                                    </button>
                                                    <button onClick={() => openEdit("topic", topic.id, topic.name, "", subject.id, block.id)}
                                                      className="flex size-5 items-center justify-center rounded-full hover:bg-muted text-muted-foreground" title="Rename topic">
                                                      <Edit2 className="size-2.5" />
                                                    </button>
                                                    <button onClick={() => setDeleteConfirm({ type: "topic", id: topic.id, name: topic.name })}
                                                      className="flex size-5 items-center justify-center rounded-full hover:bg-destructive/10 text-muted-foreground hover:text-destructive" title="Delete topic">
                                                      <Trash2 className="size-2.5" />
                                                    </button>
                                                  </div>

                                                  {/* Slides under Topic */}
                                                  {isTopicExpanded && (
                                                    <div className="pb-2.5 pl-20 pr-5 space-y-1 bg-background/5">
                                                      {topic.slides.map((slide) => (
                                                        <div key={slide.id}
                                                          className="flex items-center gap-2 rounded-xl border border-border/50 bg-background px-3 py-1.5 text-[11px]">
                                                          {slideIcon(slide.file_type)}
                                                          <span className="flex-1 truncate text-foreground font-medium">{slide.title}</span>
                                                          <span className="shrink-0 text-muted-foreground capitalize text-[9px]">{slide.file_type}</span>
                                                          <button
                                                            onClick={() => setDeleteConfirm({ type: "slide", id: slide.id, name: slide.title })}
                                                            className="ml-1 flex size-5 shrink-0 items-center justify-center rounded-full hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                                                            title="Delete slide"
                                                          >
                                                            <Trash2 className="size-2.5" />
                                                          </button>
                                                        </div>
                                                      ))}
                                                    </div>
                                                  )}
                                                </div>
                                              );
                                            })}

                                            {/* General Slides under Sub-block (not in any topic/section) */}
                                            {subBlockGeneralSlides.length > 0 && (
                                              <div className="pb-2.5 pl-14 pr-5 pt-1 space-y-1">
                                                <p className="text-[10px] text-muted-foreground/60 italic px-1 mb-1">General Slides</p>
                                                {subBlockGeneralSlides.map((slide) => (
                                                  <div key={slide.id}
                                                    className="flex items-center gap-2 rounded-xl border border-border/50 bg-background px-3 py-1.5 text-[11px]">
                                                    {slideIcon(slide.file_type)}
                                                    <span className="flex-1 truncate text-foreground font-medium">{slide.title}</span>
                                                    <span className="shrink-0 text-muted-foreground capitalize text-[9px]">{slide.file_type}</span>
                                                    <button
                                                      onClick={() => setDeleteConfirm({ type: "slide", id: slide.id, name: slide.title })}
                                                      className="ml-1 flex size-5 shrink-0 items-center justify-center rounded-full hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                                                      title="Delete slide"
                                                    >
                                                      <Trash2 className="size-2.5" />
                                                    </button>
                                                  </div>
                                                ))}
                                              </div>
                                            )}

                                            {subBlockSlides.length === 0 && (
                                              <p className="py-2.5 pl-14 text-xs text-muted-foreground/60 italic">No topics or slides uploaded yet.</p>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                    );
                                  })}

                                  {/* Render Direct Topics under Block (Level 4, where sub_block is null) */}
                                  {directTopics.map((topic) => {
                                    const isTopicExpanded = expandedTopics.has(topic.id);
                                    return (
                                      <div key={topic.id} className="border-b border-border/40 last:border-0">
                                        {/* Topic Row */}
                                        <div className="flex items-center gap-3 px-5 py-2 pl-14 bg-background/10">
                                          <button
                                            onClick={() => setExpandedTopics((prev) => {
                                              const s = new Set(prev);
                                              isTopicExpanded ? s.delete(topic.id) : s.add(topic.id);
                                              return s;
                                            })}
                                            className="flex flex-1 items-center gap-2 text-left"
                                          >
                                            <span className="size-1.5 rounded-full bg-primary/70 shrink-0" />
                                            <p className="text-xs text-muted-foreground font-medium">{topic.name}</p>
                                            <span className="text-[10px] text-muted-foreground/60">
                                              ({topic.slides.length} slide{topic.slides.length !== 1 ? "s" : ""})
                                            </span>
                                            <div className="ml-auto mr-1 text-muted-foreground">
                                              {isTopicExpanded ? <ChevronDown className="size-2.5" /> : <ChevronRight className="size-2.5" />}
                                            </div>
                                          </button>
                                          <button onClick={() => openEdit("topic", topic.id, topic.name, "", subject.id, block.id)}
                                            className="flex size-5 items-center justify-center rounded-full hover:bg-muted text-muted-foreground" title="Rename topic">
                                            <Edit2 className="size-2.5" />
                                          </button>
                                          <button onClick={() => setDeleteConfirm({ type: "topic", id: topic.id, name: topic.name })}
                                            className="flex size-5 items-center justify-center rounded-full hover:bg-destructive/10 text-muted-foreground hover:text-destructive" title="Delete topic">
                                            <Trash2 className="size-2.5" />
                                          </button>
                                        </div>

                                        {/* Slides under Direct Topic */}
                                        {isTopicExpanded && (
                                          <div className="pb-2.5 pl-20 pr-5 space-y-1 bg-background/5">
                                            {topic.slides.map((slide) => (
                                              <div key={slide.id}
                                                className="flex items-center gap-2 rounded-xl border border-border/50 bg-background px-3 py-1.5 text-[11px]">
                                                {slideIcon(slide.file_type)}
                                                <span className="flex-1 truncate text-foreground font-medium">{slide.title}</span>
                                                <span className="shrink-0 text-muted-foreground capitalize text-[9px]">{slide.file_type}</span>
                                                <button
                                                  onClick={() => setDeleteConfirm({ type: "slide", id: slide.id, name: slide.title })}
                                                  className="ml-1 flex size-5 shrink-0 items-center justify-center rounded-full hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                                                  title="Delete slide"
                                                >
                                                  <Trash2 className="size-2.5" />
                                                </button>
                                              </div>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    );
                                  })}

                                  {/* Direct General Slides under Block (sub_block is null, topic is null) */}
                                  {directGeneralSlides.length > 0 && (
                                    <div className="pb-2.5 pl-14 pr-5 pt-1 space-y-1">
                                      <p className="text-[10px] text-muted-foreground/60 italic px-1 mb-1">General Slides</p>
                                      {directGeneralSlides.map((slide) => (
                                        <div key={slide.id}
                                          className="flex items-center gap-2 rounded-xl border border-border/50 bg-background px-3 py-1.5 text-[11px]">
                                          {slideIcon(slide.file_type)}
                                          <span className="flex-1 truncate text-foreground font-medium">{slide.title}</span>
                                          <span className="shrink-0 text-muted-foreground capitalize text-[9px]">{slide.file_type}</span>
                                          <button
                                            onClick={() => setDeleteConfirm({ type: "slide", id: slide.id, name: slide.title })}
                                            className="ml-1 flex size-5 shrink-0 items-center justify-center rounded-full hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                                            title="Delete slide"
                                          >
                                            <Trash2 className="size-2.5" />
                                          </button>
                                        </div>
                                      ))}
                                    </div>
                                  )}

                                  {subBlocks.length === 0 && directTopics.length === 0 && directGeneralSlides.length === 0 && !loadingSlides && (
                                    <p className="py-3.5 pl-14 text-xs text-muted-foreground/60 italic">No sub-blocks or topics created yet.</p>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}

                        {/* Add block button */}
                        <button onClick={() => openAddBlock(subject.id)}
                          className="flex w-full items-center gap-2 px-5 py-3 pl-10 text-sm text-primary hover:bg-primary/5 transition-colors">
                          <Plus className="size-4" /> Add block to {subject.name}
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Add / Edit Modal ───────────────────────────────────────────────────── */}
      {form.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setForm(CLOSED_FORM)} />
          <div className="relative z-10 w-full max-w-sm rounded-3xl border border-border bg-card p-6 shadow-2xl">
            <div className="mb-5 flex items-center justify-between">
              <h2 className="font-serif text-xl capitalize">
                {form.mode === "add" ? "Add" : "Edit"}{" "}
                {form.type === "sub-block" ? "Sub-block" : form.type}
              </h2>
              <button onClick={() => setForm(CLOSED_FORM)}
                className="flex size-8 items-center justify-center rounded-full border border-border text-muted-foreground hover:text-foreground">
                <X className="size-4" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Name</label>
                <input type="text" value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder={
                    form.type === "subject"
                      ? "e.g. Anatomy"
                      : form.type === "block"
                      ? "e.g. Block 1"
                      : form.type === "sub-block"
                      ? "e.g. Gross Anatomy"
                      : "e.g. Upper Limb"
                  }
                  className="mt-1.5 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary"
                  autoFocus
                />
              </div>
              {form.type !== "topic" && (
                <div>
                  <label className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Description <span className="text-[9px] text-muted-foreground/60">(optional)</span></label>
                  <input type="text" value={form.description}
                    onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                    placeholder="Brief description"
                    className="mt-1.5 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary"
                  />
                </div>
              )}
              {error && <p className="text-xs text-destructive">{error}</p>}
              <button onClick={handleSave} disabled={!form.name.trim() || saving}
                className="inline-flex h-11 w-full items-center justify-center rounded-full bg-primary text-sm font-medium text-primary-foreground disabled:opacity-40 hover:opacity-90">
                {saving ? <Loader2 className="size-4 animate-spin" /> : form.mode === "add" ? "Add" : "Save changes"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Delete Confirm Modal ───────────────────────────────────────────────── */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setDeleteConfirm(null)} />
          <div className="relative z-10 w-full max-w-sm rounded-3xl border border-border bg-card p-6 shadow-2xl">
            <h2 className="font-serif text-xl mb-2 capitalize">Delete {deleteConfirm.type === "sub-block" ? "Sub-block" : deleteConfirm.type}?</h2>
            <p className="text-sm text-muted-foreground mb-5">
              <span className="font-medium text-foreground">{deleteConfirm.name}</span>{" "}
              {deleteConfirm.type === "slide"
                ? "will be permanently deleted from the curriculum. Students will lose access."
                : "and all its contents will be permanently deleted. This cannot be undone."}
            </p>
            <div className="flex gap-3">
              <button onClick={() => setDeleteConfirm(null)}
                className="flex-1 h-10 rounded-full border border-border text-sm font-medium hover:bg-muted">Cancel</button>
              <button onClick={handleDelete} disabled={saving}
                className="flex-1 h-10 rounded-full bg-destructive text-sm font-medium text-white hover:opacity-90 disabled:opacity-40">
                {saving ? <Loader2 className="size-4 animate-spin mx-auto" /> : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </AuthGuard>
  );
}
