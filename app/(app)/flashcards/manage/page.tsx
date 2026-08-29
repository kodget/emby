"use client";

import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Search, Pencil, Trash2, RotateCcw } from "lucide-react";
import { flashcardApi, type Flashcard } from "@/lib/api";
import { loadCurriculum, type SubjectId, type BlockId, type Subject } from "@/lib/curriculum";
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
  // These two mirror the API fields they are submitted as. They were previously named
  // "topic"/"section", one level off from the curriculum, which is how a Topic id ended
  // up being written into the sub_block foreign key.
  const [selectedSubBlock, setSelectedSubBlock] = useState<string | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);

  useEffect(() => {
    loadCurriculum().then(setCurriculum).catch(console.error);
  }, []);

  const subject = selectedSubject ? curriculum.find((s) => s.id === selectedSubject) : null;
  const blocks = subject?.blocks || [];
  const block = selectedBlock ? blocks.find((b) => b.id === selectedBlock) : null;
  const subBlocks = block?.subBlocks || [];
  const subBlockObj = selectedSubBlock
    ? subBlocks.find((sb) => String(sb.id) === selectedSubBlock)
    : null;
  // Topics hang off the chosen sub-block; a block can also own topics directly, which
  // are the right list when no sub-block is picked.
  const topics = subBlockObj ? subBlockObj.topics : block?.topics || [];

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
    setSelectedSubBlock(card.sub_block?.toString() || null);
    setSelectedTopic(card.topic?.toString() || null);
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
        sub_block: selectedSubBlock ? Number(selectedSubBlock) : null,
        topic: selectedTopic ? Number(selectedTopic) : null,
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
    <div className="min-h-screen">
      {/* Header */}
      <div className="px-6 pt-8 pb-6 max-w-4xl mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <Link
              href="/flashcards"
              className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors text-sm"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </Link>
            <div>
              <h1 className="text-2xl font-bold text-foreground">Manage Flashcards</h1>
              <p className="text-muted-foreground text-sm">{count} card{count === 1 ? "" : "s"} total</p>
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
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            id="flashcard-search"
            placeholder="Search cards..."
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            className="pl-10 bg-card border-border text-foreground placeholder:text-muted-foreground"
          />
        </div>

        {/* Cards list */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          </div>
        ) : error ? (
          <div className="text-center py-12">
            <p className="text-destructive">{error}</p>
            <button onClick={() => load()} className="mt-3 text-sm text-muted-foreground hover:text-foreground underline">
              Retry
            </button>
          </div>
        ) : cards.length === 0 ? (
          <div className="text-center py-16 text-muted-foreground">
            No flashcards found.{" "}
            <button onClick={() => setCreateOpen(true)} className="text-primary underline">
              Create one
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {cards.map((card) => (
              <div
                key={card.id}
                id={`card-item-${card.id}`}
                className="rounded-2xl border border-border bg-card p-5 flex flex-col sm:flex-row sm:items-start gap-4"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border
                      ${card.source === "quiz_mistake"
                        ? "bg-review/10 border-review/30 text-review"
                        : "bg-primary/10 border-primary/30 text-primary"}`}>
                      {sourceLabel[card.source] ?? card.source}
                    </span>
                    {card.subject_name && (
                      <span className="text-[10px] text-muted-foreground">{card.subject_name}</span>
                    )}
                    {card.sub_block_name && (
                      <span className="text-[10px] text-muted-foreground"> / {card.sub_block_name}</span>
                    )}
                    {card.topic_name && (
                      <span className="text-[10px] text-muted-foreground"> / {card.topic_name}</span>
                    )}
                  </div>
                  <p className="text-foreground text-sm font-medium leading-snug line-clamp-2">{card.front}</p>
                  <p className="text-muted-foreground text-sm mt-1 line-clamp-1">{card.back}</p>
                  {card.progress && (
                    <p className="text-[10px] text-muted-foreground/70 mt-1">
                      Due: {new Date(card.progress.due_date).toLocaleDateString()}
                      {" · "}{card.progress.repetitions} reviews
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    id={`edit-card-${card.id}`}
                    onClick={() => openEdit(card)}
                    className="p-2 rounded-xl bg-card hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                    aria-label="Edit card"
                  >
                    <Pencil className="w-4 h-4" />
                  </button>
                  {deleteConfirmId === card.id ? (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleDelete(card.id)}
                        className="px-3 py-1.5 text-xs rounded-lg bg-destructive text-foreground transition-colors"
                      >
                        Confirm
                      </button>
                      <button
                        onClick={() => setDeleteConfirmId(null)}
                        className="px-3 py-1.5 text-xs rounded-lg bg-muted hover:bg-muted text-foreground transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      id={`delete-card-${card.id}`}
                      onClick={() => setDeleteConfirmId(card.id)}
                      className="p-2 rounded-xl bg-card hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
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
          <div className="relative bg-card border border-border rounded-2xl p-6 w-full max-w-lg mx-4 shadow-2xl">
            <h2 className="text-lg font-semibold text-foreground mb-4">Edit Flashcard</h2>
            <div className="flex flex-col gap-4">
              <div className="space-y-3">
                <div>
                  <Label className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Subject</Label>
                  <div className="mt-1.5 grid grid-cols-3 gap-2">
                    {curriculum.map((subj) => (
                      <button
                        key={subj.id}
                        type="button"
                        onClick={() => {
                          setSelectedSubject(subj.id);
                          setSelectedBlock(null);
                          setSelectedSubBlock(null);
                          setSelectedTopic(null);
                        }}
                        className={`rounded-lg border px-2 py-1.5 text-xs transition-colors ${
                          selectedSubject === subj.id
                            ? "border-primary bg-primary/12 text-primary"
                            : "border-border bg-card hover:border-primary/45"
                        }`}
                      >
                        {subj.title}
                      </button>
                    ))}
                  </div>
                </div>

                {selectedSubject && blocks.length > 0 && (
                  <div>
                    <Label className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">Block</Label>
                    <div className="mt-1.5 grid grid-cols-2 gap-2">
                      {blocks.map((blk) => (
                        <button
                          key={blk.id}
                          type="button"
                          onClick={() => {
                            setSelectedBlock(blk.id);
                            setSelectedSubBlock(null);
                            setSelectedTopic(null);
                          }}
                          className={`rounded-lg border px-2 py-1.5 text-xs transition-colors ${
                            selectedBlock === blk.id
                              ? "border-primary bg-primary/12 text-primary"
                              : "border-border bg-card hover:border-primary/45"
                          }`}
                        >
                          {blk.title}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {selectedBlock && subBlocks.length > 0 && (
                  <div>
                    <Label className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
                      Sub-block <span className="text-[9px] opacity-60">(Optional)</span>
                    </Label>
                    <div className="mt-1.5 grid grid-cols-2 gap-2">
                      {subBlocks.map((sb) => (
                        <button
                          key={sb.id}
                          type="button"
                          onClick={() => {
                            setSelectedSubBlock(
                              selectedSubBlock === String(sb.id) ? null : String(sb.id),
                            );
                            setSelectedTopic(null);
                          }}
                          className={`rounded-lg border px-2 py-1.5 text-xs transition-colors ${
                            selectedSubBlock === String(sb.id)
                              ? "border-primary bg-primary/12 text-primary"
                              : "border-border bg-card hover:border-primary/45"
                          }`}
                        >
                          {sb.title}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {selectedBlock && topics.length > 0 && (
                  <div>
                    <Label className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
                      Topic <span className="text-[9px] opacity-60">(Optional)</span>
                    </Label>
                    <div className="mt-1.5 grid grid-cols-2 gap-2">
                      {topics.map((topicItem) => (
                        <button
                          key={topicItem.id}
                          type="button"
                          onClick={() =>
                            setSelectedTopic(
                              selectedTopic === String(topicItem.id)
                                ? null
                                : String(topicItem.id),
                            )
                          }
                          className={`rounded-lg border px-2 py-1.5 text-xs transition-colors ${
                            selectedTopic === String(topicItem.id)
                              ? "border-primary bg-primary/12 text-primary"
                              : "border-border bg-card hover:border-primary/45"
                          }`}
                        >
                          {topicItem.title}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div>
                <label className="text-muted-foreground text-sm block mb-1">Front</label>
                <textarea
                  value={editFront}
                  onChange={(e) => setEditFront(e.target.value)}
                  className="w-full min-h-[70px] bg-card border border-border rounded-xl text-foreground text-sm p-3 resize-none outline-none focus:border-primary/50"
                />
              </div>
              <div>
                <label className="text-muted-foreground text-sm block mb-1">Back</label>
                <textarea
                  value={editBack}
                  onChange={(e) => setEditBack(e.target.value)}
                  className="w-full min-h-[70px] bg-card border border-border rounded-xl text-foreground text-sm p-3 resize-none outline-none focus:border-primary/50"
                />
              </div>
              <div>
                <label className="text-muted-foreground text-sm block mb-1">Explanation</label>
                <textarea
                  value={editExplanation}
                  onChange={(e) => setEditExplanation(e.target.value)}
                  className="w-full min-h-[50px] bg-card border border-border rounded-xl text-foreground text-sm p-3 resize-none outline-none focus:border-primary/50"
                />
              </div>
              <div className="flex gap-3 justify-end pt-1">
                <button
                  onClick={() => setEditCard(null)}
                  className="px-4 py-2 rounded-xl bg-muted hover:bg-muted text-foreground text-sm transition-colors"
                >
                  Cancel
                </button>
                <button
                  id="save-edit-card"
                  disabled={editLoading}
                  onClick={saveEdit}
                  className="px-5 py-2 rounded-xl bg-primary text-primary-foreground text-foreground text-sm font-medium transition-all disabled:opacity-50"
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
    <Suspense fallback={<div className="min-h-screen bg-background flex items-center justify-center"><div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" /></div>}>
      <ManageFlashcardsContent />
    </Suspense>
  );
}
