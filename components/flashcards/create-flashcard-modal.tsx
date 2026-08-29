"use client";

/**
 * Create a flashcard by hand.
 *
 * The categorisation here used to be wrong in a way that quietly corrupted data. The
 * curriculum is Subject -> Block -> SubBlock -> Topic, and `loadCurriculum()` builds
 * `block.subBlocks[]` (each carrying its own `topics[]`) alongside `block.topics[]` for
 * topics that hang directly off a block. The old form ignored `subBlocks` entirely: it
 * listed `block.topics`, labelled them "Topic", and then submitted the chosen id as
 * `sub_block` — a Topic primary key written into a SubBlock foreign key. It then offered
 * a "Section" picker reading `topic.sections`, a field that does not exist on any type or
 * any API response, so it never rendered and the real `topic` field could never be set.
 *
 * This walks the actual hierarchy. Sub-block and topic are both optional, because a card
 * filed at block level is better than one filed under the wrong parent.
 */

import { useEffect, useState } from "react";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { flashcardApi, type Flashcard } from "@/lib/api";
import {
  loadCurriculum,
  type BlockId,
  type Subject,
  type SubjectId,
} from "@/lib/curriculum";
import { cn } from "@/lib/utils";

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
  const [selectedSubBlock, setSelectedSubBlock] = useState<string | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);

  useEffect(() => {
    if (open) loadCurriculum().then(setCurriculum).catch(console.error);
  }, [open]);

  const subject = selectedSubject
    ? curriculum.find((s) => s.id === selectedSubject)
    : null;
  const blocks = subject?.blocks ?? [];
  const block = selectedBlock ? blocks.find((b) => b.id === selectedBlock) : null;
  const subBlocks = block?.subBlocks ?? [];
  const subBlock = selectedSubBlock
    ? subBlocks.find((sb) => String(sb.id) === selectedSubBlock)
    : null;

  // Topics live under the chosen sub-block; a block can also own topics directly, and
  // those are the right list to show when no sub-block is selected.
  const topics = subBlock ? subBlock.topics : (block?.topics ?? []);

  const reset = () => {
    setFront("");
    setBack("");
    setExplanation("");
    setError("");
    setSelectedSubject(null);
    setSelectedBlock(null);
    setSelectedSubBlock(null);
    setSelectedTopic(null);
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
        sub_block: selectedSubBlock ? Number(selectedSubBlock) : undefined,
        topic: selectedTopic ? Number(selectedTopic) : undefined,
      });
      onCreated?.(card);
      reset();
      setOpen(false);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Could not create the card.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) reset();
      }}
    >
      <DialogTrigger asChild>
        {trigger ?? (
          <Button id="create-flashcard-btn" className="press gap-2 rounded-full">
            <Plus className="size-4" />
            New card
          </Button>
        )}
      </DialogTrigger>

      <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display text-lg">Create a flashcard</DialogTitle>
        </DialogHeader>

        <div className="mt-1 flex flex-col gap-4">
          <ChipGroup label="Subject">
            {curriculum.map((subj) => (
              <Chip
                key={subj.id}
                selected={selectedSubject === subj.id}
                onClick={() => {
                  setSelectedSubject(subj.id);
                  setSelectedBlock(null);
                  setSelectedSubBlock(null);
                  setSelectedTopic(null);
                }}
              >
                {subj.title}
              </Chip>
            ))}
          </ChipGroup>

          {selectedSubject && blocks.length > 0 && (
            <ChipGroup label="Block">
              {blocks.map((blk) => (
                <Chip
                  key={blk.id}
                  selected={selectedBlock === blk.id}
                  onClick={() => {
                    setSelectedBlock(blk.id);
                    setSelectedSubBlock(null);
                    setSelectedTopic(null);
                  }}
                >
                  {blk.title}
                </Chip>
              ))}
            </ChipGroup>
          )}

          {selectedBlock && subBlocks.length > 0 && (
            <ChipGroup label="Sub-block" optional>
              {subBlocks.map((sb) => (
                <Chip
                  key={sb.id}
                  selected={selectedSubBlock === String(sb.id)}
                  onClick={() => {
                    setSelectedSubBlock(
                      selectedSubBlock === String(sb.id) ? null : String(sb.id),
                    );
                    setSelectedTopic(null);
                  }}
                >
                  {sb.title}
                </Chip>
              ))}
            </ChipGroup>
          )}

          {selectedBlock && topics.length > 0 && (
            <ChipGroup label="Topic" optional>
              {topics.map((topic) => (
                <Chip
                  key={topic.id}
                  selected={selectedTopic === String(topic.id)}
                  onClick={() =>
                    setSelectedTopic(
                      selectedTopic === String(topic.id) ? null : String(topic.id),
                    )
                  }
                >
                  {topic.title}
                </Chip>
              ))}
            </ChipGroup>
          )}

          <Field
            id="fc-front"
            label="Front (question)"
            placeholder="Type the question or prompt…"
            value={front}
            onChange={setFront}
            minHeight={80}
          />
          <Field
            id="fc-back"
            label="Back (answer)"
            placeholder="Type the answer…"
            value={back}
            onChange={setBack}
            minHeight={80}
          />
          <Field
            id="fc-explanation"
            label="Explanation (optional)"
            placeholder="Add extra context…"
            value={explanation}
            onChange={setExplanation}
            minHeight={60}
          />

          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" onClick={() => setOpen(false)} className="rounded-full">
              Cancel
            </Button>
            <Button
              id="create-flashcard-submit"
              disabled={loading}
              onClick={handleCreate}
              className="press rounded-full"
            >
              {loading ? "Creating…" : "Create card"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ChipGroup({
  label,
  optional = false,
  children,
}: {
  label: string;
  optional?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <Label className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
        {label}
        {optional && <span className="ml-1 opacity-60">(optional)</span>}
      </Label>
      <div className="mt-1.5 flex flex-wrap gap-1.5">{children}</div>
    </div>
  );
}

function Chip({
  selected,
  onClick,
  children,
}: {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={cn(
        "press rounded-full border px-3 py-1.5 text-xs transition-colors",
        selected
          ? "border-primary bg-primary/12 text-primary"
          : "border-border bg-card text-foreground hover:border-primary/45",
      )}
    >
      {children}
    </button>
  );
}

function Field({
  id,
  label,
  placeholder,
  value,
  onChange,
  minHeight,
}: {
  id: string;
  label: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  minHeight: number;
}) {
  return (
    <div>
      <Label className="mb-1.5 block text-sm text-muted-foreground">{label}</Label>
      <Textarea
        id={id}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="resize-none"
        style={{ minHeight }}
      />
    </div>
  );
}
