"use client";

import { useState, useEffect } from "react";
import { Plus, X } from "lucide-react";
import { flashcardApi, type Flashcard } from "@/lib/api";
import { loadCurriculum, type SubjectId, type BlockId, type TopicId, type Subject } from "@/lib/curriculum";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

interface CreateFlashcardModalProps {
  onCreated?: (card: Flashcard) => void;
  trigger?: React.ReactNode;
  open?: boolean;
  onOpenChange?: (v: boolean) => void;
}

export function CreateFlashcardModal({
  onCreated,
  trigger,
  open: externalOpen,
  onOpenChange,
}: CreateFlashcardModalProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const open = externalOpen !== undefined ? externalOpen : internalOpen;
  const setOpen = onOpenChange ?? setInternalOpen;

  const [front, setFront] = useState("");
  const [back, setBack] = useState("");
  const [explanation, setExplanation] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [curriculum, setCurriculum] = useState<Subject[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<SubjectId | null>(null);
  const [selectedBlock, setSelectedBlock] = useState<BlockId | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<TopicId | null>(null);
  const [selectedSection, setSelectedSection] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      loadCurriculum().then(setCurriculum).catch(console.error);
    }
  }, [open]);

  const subject = selectedSubject ? curriculum.find((s) => s.id === selectedSubject) : null;
  const blocks = subject?.blocks || [];
  const block = selectedBlock ? blocks.find((b) => b.id === selectedBlock) : null;
  const topics = block?.topics || [];
  const topicObj = selectedTopic ? topics.find((t) => t.id === selectedTopic) : null;
  const sections = topicObj?.sections || [];

  const reset = () => {
    setFront("");
    setBack("");
    setExplanation("");
    setError("");
    setSelectedSubject(null);
    setSelectedBlock(null);
    setSelectedTopic(null);
    setSelectedSection(null);
  };

  const handleCreate = async () => {
    if (!front.trim() || !back.trim()) {
      setError("Front and back are required.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const card = await flashcardApi.create({
        front: front.trim(),
        back: back.trim(),
        explanation: explanation.trim(),
        subject: selectedSubject || undefined,
        block: selectedBlock || undefined,
        sub_block: selectedTopic ? Number(selectedTopic) : undefined,
        topic: selectedSection ? Number(selectedSection) : undefined,
      });
      onCreated?.(card);
      reset();
      setOpen(false);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Failed to create flashcard.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) reset(); }}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button id="create-flashcard-btn" className="flex items-center gap-2 bg-gradient-to-r from-violet-600 to-violet-500 hover:from-violet-500 hover:to-violet-400 border-0">
            <Plus className="w-4 h-4" />
            New Card
          </Button>
        )}
      </DialogTrigger>

      <DialogContent className="bg-[#0f1729] border border-white/10 text-white max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold text-white">Create Flashcard</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4 mt-2">
          {/* Categorization */}
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
                  {topics.map((topic) => (
                    <button
                      key={topic.id}
                      type="button"
                      onClick={() => {
                        setSelectedTopic(topic.id);
                        setSelectedSection(null);
                      }}
                      className={`rounded-lg border px-2 py-1.5 text-xs transition-colors ${
                        selectedTopic === topic.id
                          ? "border-violet-500 bg-violet-500/20 text-violet-300"
                          : "border-white/10 bg-white/5 hover:border-violet-500/50"
                      }`}
                    >
                      {topic.title}
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

          <div className="mt-2">
            <Label className="text-white/70 text-sm mb-1.5 block">Front (Question)</Label>
            <Textarea
              id="fc-front"
              placeholder="Type the question or prompt..."
              value={front}
              onChange={(e) => setFront(e.target.value)}
              className="bg-white/5 border-white/10 text-white placeholder:text-white/30 resize-none min-h-[80px]"
            />
          </div>

          <div>
            <Label className="text-white/70 text-sm mb-1.5 block">Back (Answer)</Label>
            <Textarea
              id="fc-back"
              placeholder="Type the answer..."
              value={back}
              onChange={(e) => setBack(e.target.value)}
              className="bg-white/5 border-white/10 text-white placeholder:text-white/30 resize-none min-h-[80px]"
            />
          </div>

          <div>
            <Label className="text-white/70 text-sm mb-1.5 block">Explanation (optional)</Label>
            <Textarea
              id="fc-explanation"
              placeholder="Add extra context or explanation..."
              value={explanation}
              onChange={(e) => setExplanation(e.target.value)}
              className="bg-white/5 border-white/10 text-white placeholder:text-white/30 resize-none min-h-[60px]"
            />
          </div>

          {error && <p className="text-red-400 text-sm">{error}</p>}

          <div className="flex gap-3 justify-end pt-2">
            <Button
              variant="ghost"
              onClick={() => setOpen(false)}
              className="text-white/60 hover:text-white hover:bg-white/10"
            >
              Cancel
            </Button>
            <Button
              id="create-flashcard-submit"
              disabled={loading}
              onClick={handleCreate}
              className="bg-gradient-to-r from-violet-600 to-violet-500 hover:from-violet-500 hover:to-violet-400 border-0"
            >
              {loading ? "Creating..." : "Create Card"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
