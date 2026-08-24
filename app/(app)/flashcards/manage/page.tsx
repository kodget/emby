"use client";

import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Search, Pencil, Trash2, RotateCcw } from "lucide-react";
import { flashcardApi, type Flashcard } from "@/lib/api";
import { loadCurriculum, type SubjectId, type BlockId, type TopicId, type Subject } from "@/lib/curriculum";
import { CreateFlashcardModal } from "@/components/flashcards/create-flashcard-modal";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { Suspense } from "react";

function ManageFlashcardsContent() {
  const params = useSearchParams();
  const [cards, setCards] = useState<Flashcard[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(params.get("create") === "1");
  const [editCard, setEditCard] = useState<Flashcard | null>(null);
  const [editFront, setEditFront] = useState("");
  const [editBack, setEditBack] = useState("");
  const [editExplanation, setEditExplanation] = useState("");
  const [editLoading, setEditLoading] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);

  const [curriculum, setCurriculum] = useState<Subject[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<SubjectId | null>(null);
  const [selectedBlock, setSelectedBlock] = useState<BlockId | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<TopicId | null>(null);
  const [selectedSection, setSelectedSection] = useState<string | null>(null);

  useEffect(() => {
    loadCurriculum().then(setCurriculum).catch(console.error);
  }, []);

  const subject = selectedSubject ? curriculum.find((s) => s.id === selectedSubject) : null;
  const blocks = subject?.blocks || [];
  const block = selectedBlock ? blocks.find((b) => b.id === selectedBlock) : null;
  const topics = block?.topics || [];
  const topicObj = selectedTopic ? topics.find((t) => t.id === selectedTopic) : null;
  const sections = topicObj?.sections || [];

  const load = useCallback(async (q?: string) => {
    setLoading(true);
    setError("");
    try {
      const data = await flashcardApi.getAll({ search: q || undefined });
      setCards(data.results);
      setCount(data.count);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Failed to load cards.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSearch = (v: string) => {
    setSearch(v);
    load(v);
  };

  const handleDelete = async (id: number) => {
    try {
      await flashcardApi.delete(id);
      setCards((prev) => prev.filter((c) => c.id !== id));
      setCount((n) => n - 1);
    } catch {
      alert("Failed to delete card.");
    } finally {
      setDeleteConfirmId(null);
    }
  };

  const openEdit = (card: Flashcard) => {
    setEditCard(card);
    setEditFront(card.front);
    setEditBack(card.back);
    setEditExplanation(card.explanation);
    setSelectedSubject(card.subject || null);
    setSelectedBlock(card.block || null);
    setSelectedTopic(card.sub_block?.toString() || null);
    setSelectedSection(card.topic?.toString() || null);
  };

  const saveEdit = async () => {
    if (!editCard) return;
    setEditLoading(true);
    try {
      const updated = await flashcardApi.update(editCard.id, {
        front: editFront,
        back: editBack,
        explanation: editExplanation,
        subject: selectedSubject || null,
        block: selectedBlock || null,
        sub_block: selectedTopic ? Number(selectedTopic) : null,
        topic: selectedSection ? Number(selectedSection) : null,
      });
      setCards((prev) => prev.map((c) => c.id === updated.id ? updated : c));
      setEditCard(null);
    } catch {
      alert("Failed to save.");
    } finally {
      setEditLoading(false);
    }
  };

  const sourceLabel: Record<string, string> = {
    manual: "Manual",
    quiz_mistake: "Quiz Mistake",
    ai: "AI",
    pdf: "PDF",
    lecture_note: "Lecture Note",
  };

  return (
    <div className="min-h-screen bg-[#080d1a] text-white">
      {/* Header */}
      <div className="px-6 pt-8 pb-6 max-w-4xl mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <Link
              href="/flashcards"
              className="flex items-center gap-2 text-white/50 hover:text-white transition-colors text-sm"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </Link>
            <div>
              <h1 className="text-2xl font-bold text-white">Manage Flashcards</h1>
              <p className="text-white/40 text-sm">{count} cards total</p>
            </div>
          </div>
          <CreateFlashcardModal
            open={createOpen}
            onOpenChange={setCreateOpen}
            onCreated={(card) => {
              setCards((prev) => [card, ...prev]);
              setCount((n) => n + 1);
              setCreateOpen(false);
            }}
          />
        </div>
      </div>

      <div className="px-6 pb-8 max-w-4xl mx-auto space-y-5">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
          <Input
            id="flashcard-search"
            placeholder="Search cards..."
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/30"
          />
        </div>

        {/* Cards list */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 rounded-full border-2 border-violet-500 border-t-transparent animate-spin" />
          </div>
        ) : error ? (
          <div className="text-center py-12">
            <p className="text-red-400">{error}</p>
            <button onClick={() => load()} className="mt-3 text-sm text-white/60 hover:text-white underline">
              Retry
            </button>
          </div>
        ) : cards.length === 0 ? (
          <div className="text-center py-16 text-white/40">
            No flashcards found.{" "}
            <button onClick={() => setCreateOpen(true)} className="text-violet-400 underline">
              Create one
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {cards.map((card) => (
              <div
                key={card.id}
                id={`card-item-${card.id}`}
                className="rounded-2xl border border-white/10 bg-white/5 p-5 flex flex-col sm:flex-row sm:items-start gap-4"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border
                      ${card.source === "quiz_mistake"
                        ? "bg-orange-900/30 border-orange-500/30 text-orange-400"
                        : "bg-violet-900/30 border-violet-500/30 text-violet-400"}`}>
                      {sourceLabel[card.source] ?? card.source}
                    </span>
                    {card.subject_name && (
                      <span className="text-[10px] text-white/30">{card.subject_name}</span>
                    )}
                    {card.sub_block_name && (
                      <span className="text-[10px] text-white/30"> / {card.sub_block_name}</span>
                    )}
                    {card.topic_name && (
                      <span className="text-[10px] text-white/30"> / {card.topic_name}</span>
                    )}
                  </div>
                  <p className="text-white text-sm font-medium leading-snug line-clamp-2">{card.front}</p>
                  <p className="text-white/50 text-sm mt-1 line-clamp-1">{card.back}</p>
                  {card.progress && (
                    <p className="text-[10px] text-white/25 mt-1">
                      Due: {new Date(card.progress.due_date).toLocaleDateString()}
                      {" · "}{card.progress.repetitions} reviews
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    id={`edit-card-${card.id}`}
                    onClick={() => openEdit(card)}
                    className="p-2 rounded-xl bg-white/5 hover:bg-white/15 text-white/50 hover:text-white transition-colors"
                    aria-label="Edit card"
                  >
                    <Pencil className="w-4 h-4" />
                  </button>
                  {deleteConfirmId === card.id ? (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleDelete(card.id)}
                        className="px-3 py-1.5 text-xs rounded-lg bg-red-600 hover:bg-red-500 text-white transition-colors"
                      >
                        Confirm
                      </button>
                      <button
                        onClick={() => setDeleteConfirmId(null)}
                        className="px-3 py-1.5 text-xs rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      id={`delete-card-${card.id}`}
                      onClick={() => setDeleteConfirmId(card.id)}
                      className="p-2 rounded-xl bg-white/5 hover:bg-red-900/30 text-white/50 hover:text-red-400 transition-colors"
                      aria-label="Delete card"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Edit Modal (inline slide-over style) */}
      {editCard && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setEditCard(null)} />
          <div className="relative bg-[#0f1729] border border-white/10 rounded-2xl p-6 w-full max-w-lg mx-4 shadow-2xl">
            <h2 className="text-lg font-semibold text-white mb-4">Edit Flashcard</h2>
            <div className="flex flex-col gap-4">
              <div className="space-y-3">
                <div>
                  <Label className="text-[11px] font-medium uppercase tracking-widest text-white/50">Subject</Label>
                  <div className="mt-1.5 grid grid-cols-3 gap-2">
                    {curriculum.map((subj) => (
                      <button
                        key={subj.id}
                        type="button"
                        onClick={() => {
                          setSelectedSubject(subj.id);
                          setSelectedBlock(null);
                          setSelectedTopic(null);
                          setSelectedSection(null);
                        }}
                        className={`rounded-lg border px-2 py-1.5 text-xs transition-colors ${
                          selectedSubject === subj.id
                            ? "border-violet-500 bg-violet-500/20 text-violet-300"
                            : "border-white/10 bg-white/5 hover:border-violet-500/50"
                        }`}
                      >
                        {subj.title}
                      </button>
                    ))}
                  </div>
                </div>

                {selectedSubject && blocks.length > 0 && (
                  <div>
                    <Label className="text-[11px] font-medium uppercase tracking-widest text-white/50">Block</Label>
                    <div className="mt-1.5 grid grid-cols-2 gap-2">
                      {blocks.map((blk) => (
                        <button
                          key={blk.id}
                          type="button"
                          onClick={() => {
                            setSelectedBlock(blk.id);
                            setSelectedTopic(null);
                            setSelectedSection(null);
                          }}
                          className={`rounded-lg border px-2 py-1.5 text-xs transition-colors ${
                            selectedBlock === blk.id
                              ? "border-violet-500 bg-violet-500/20 text-violet-300"
                              : "border-white/10 bg-white/5 hover:border-violet-500/50"
                          }`}
                        >
                          {blk.title}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {selectedBlock && topics.length > 0 && (
                  <div>
                    <Label className="text-[11px] font-medium uppercase tracking-widest text-white/50">
                      Topic <span className="text-[9px] opacity-60">(Optional)</span>
                    </Label>
                    <div className="mt-1.5 grid grid-cols-2 gap-2">
                      {topics.map((topicItem) => (
                        <button
                          key={topicItem.id}
                          type="button"
                          onClick={() => {
                            setSelectedTopic(topicItem.id);
                            setSelectedSection(null);
                          }}
                          className={`rounded-lg border px-2 py-1.5 text-xs transition-colors ${
                            selectedTopic === topicItem.id
                              ? "border-violet-500 bg-violet-500/20 text-violet-300"
                              : "border-white/10 bg-white/5 hover:border-violet-500/50"
                          }`}
                        >
                          {topicItem.title}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {selectedTopic && sections.length > 0 && (
                  <div>
                    <Label className="text-[11px] font-medium uppercase tracking-widest text-white/50">
                      Section <span className="text-[9px] opacity-60">(Optional)</span>
                    </Label>
                    <div className="mt-1.5 grid grid-cols-2 gap-2">
                      {sections.map((sec) => (
                        <button
                          key={sec.id}
                          type="button"
                          onClick={() => setSelectedSection(sec.id)}
                          className={`rounded-lg border px-2 py-1.5 text-xs transition-colors ${
                            selectedSection === sec.id
                              ? "border-violet-500 bg-violet-500/20 text-violet-300"
                              : "border-white/10 bg-white/5 hover:border-violet-500/50"
                          }`}
                        >
                          {sec.title}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div>
                <label className="text-white/60 text-sm block mb-1">Front</label>
                <textarea
                  value={editFront}
                  onChange={(e) => setEditFront(e.target.value)}
                  className="w-full min-h-[70px] bg-white/5 border border-white/10 rounded-xl text-white text-sm p-3 resize-none outline-none focus:border-violet-500/50"
                />
              </div>
              <div>
                <label className="text-white/60 text-sm block mb-1">Back</label>
                <textarea
                  value={editBack}
                  onChange={(e) => setEditBack(e.target.value)}
                  className="w-full min-h-[70px] bg-white/5 border border-white/10 rounded-xl text-white text-sm p-3 resize-none outline-none focus:border-violet-500/50"
                />
              </div>
              <div>
                <label className="text-white/60 text-sm block mb-1">Explanation</label>
                <textarea
                  value={editExplanation}
                  onChange={(e) => setEditExplanation(e.target.value)}
                  className="w-full min-h-[50px] bg-white/5 border border-white/10 rounded-xl text-white text-sm p-3 resize-none outline-none focus:border-violet-500/50"
                />
              </div>
              <div className="flex gap-3 justify-end pt-1">
                <button
                  onClick={() => setEditCard(null)}
                  className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white text-sm transition-colors"
                >
                  Cancel
                </button>
                <button
                  id="save-edit-card"
                  disabled={editLoading}
                  onClick={saveEdit}
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-violet-500 hover:from-violet-500 hover:to-violet-400 text-white text-sm font-medium transition-all disabled:opacity-50"
                >
                  {editLoading ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ManageFlashcardsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#080d1a] flex items-center justify-center"><div className="w-8 h-8 rounded-full border-2 border-violet-500 border-t-transparent animate-spin" /></div>}>
      <ManageFlashcardsContent />
    </Suspense>
  );
}
