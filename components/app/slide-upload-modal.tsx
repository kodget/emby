"use client";

import { useRef, useState, useCallback, useEffect } from "react";
import api from "@/lib/api";
import { uploadIntent, uploadOwner, type UploadIntent } from "@/lib/upload-intent";
import { motion, AnimatePresence } from "framer-motion";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faCloudArrowUp,
  faXmark,
  faFileLines,
  faCircleCheck,
  faTriangleExclamation,
  faLock,
} from "@fortawesome/free-solid-svg-icons";
import {
  useAppDispatch,
  useAppSelector,
  useCanUpload,
  useIsVerifiedClassHead,
} from "@/store/hooks";
import {
  closeUploadModal,
  addUpload,
  updateProgress,
} from "@/store/uploads-slice";
import {
  loadCurriculum,
  type SubjectId,
  type BlockId,
  type SubBlockId,
  type TopicId,
  type Subject,
} from "@/lib/curriculum";

export function SlideUploadModal() {
  const dispatch = useAppDispatch();
  const canUpload = useCanUpload();
  const isVerifiedClassHead = useIsVerifiedClassHead();
  const { isModalOpen } = useAppSelector((s) => s.uploads);
  const userName = useAppSelector((s) => s.user.name);
  const userSchool = useAppSelector((s) => s.user.school);
  const userSetName = useAppSelector((s) => s.user.setName);

  const [curriculum, setCurriculum] = useState<Subject[]>([]);
  const [loadingCurriculum, setLoadingCurriculum] = useState(true);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const intentRef = useRef<UploadIntent | null>(null);

  // Hierarchical selection state
  const [selectedSubject, setSelectedSubject] = useState<SubjectId | null>(
    null,
  );
  const [selectedBlock, setSelectedBlock] = useState<BlockId | null>(null);
  const [selectedSubBlock, setSelectedSubBlock] = useState<SubBlockId | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<TopicId | null>(null);
  const [customTopicName, setCustomTopicName] = useState("");

  // Load curriculum from API
  useEffect(() => {
    if (isModalOpen) {
      setErrorMsg("");
      setLoadingCurriculum(true);
      loadCurriculum()
        .then((data) => {
          setCurriculum(data);
          setLoadingCurriculum(false);
        })
        .catch((err) => {
          console.error("Failed to load curriculum:", err);
          setErrorMsg("Failed to load courses. Please refresh.");
          setLoadingCurriculum(false);
        });
    }
  }, [isModalOpen]);

  const handleFile = useCallback(
    (f: File) => {
      if (!/\.(pdf|ppt|pptx|docx)$/i.test(f.name)) {
        setFile(null);
        setErrorMsg("Choose a PDF, PPT, PPTX or DOCX file.");
        return;
      }
      if (f.size === 0 || f.size > 100 * 1024 * 1024) {
        setFile(null);
        setErrorMsg(f.size === 0 ? "The file is empty." : "Maximum file size is 100 MB.");
        return;
      }
      setErrorMsg("");
      setFile(f);
      if (!title)
        setTitle(f.name.replace(/\.[^.]+$/, "").replace(/[-_]/g, " "));
    },
    [title],
  );

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (submitting) return;
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting || !file || !title.trim() || !selectedSubject || !selectedBlock) return;
    setSubmitting(true);
    setErrorMsg("");

    const uploadId = `upload-${Date.now()}`;

    dispatch(
      addUpload({
        id: uploadId,
        courseId: selectedSubBlock || selectedBlock,
        moduleId: selectedSubBlock || selectedBlock,
        materialId: "",
        title: title.trim(),
        fileName: file.name,
        pages: 0,
        uploadedBy: userName,
        uploadedAt: "Just now",
        status: "uploading",
        progress: 0,
        school: userSchool,
        setName: userSetName,
      }),
    );
    try {
      let topicId = selectedTopic;

      if (customTopicName.trim()) {
        const { data: newTopic } = await api.post("/api/topics/", {
          name: customTopicName.trim(),
          ...(selectedSubBlock ? { sub_block: selectedSubBlock } : {}),
          block: selectedBlock,
        });
        topicId = newTopic.id;
        setSelectedTopic(topicId);
        setCustomTopicName("");
      }

      const formData = new FormData();
      formData.append("file", file);
      formData.append("title", title.trim());
      formData.append("subject", selectedSubject);
      formData.append("block", selectedBlock);
      if (selectedSubBlock) formData.append("sub_block", selectedSubBlock);
      if (topicId) formData.append("topic", topicId);
      intentRef.current = uploadIntent(intentRef.current, file, JSON.stringify([
        uploadOwner(), title.trim(), selectedSubject, selectedBlock, selectedSubBlock, topicId,
      ]));
      formData.append("request_id", intentRef.current.requestId);

      dispatch(
        updateProgress({ id: uploadId, progress: 30, status: "uploading" }),
      );

      const { data: slideData } = await api.post("/api/slides/upload_and_process/", formData, {
        headers: { "Content-Type": undefined },
        timeout: 120000,
      });

      dispatch(
        updateProgress({
          id: uploadId,
          progress: 50,
          status: "downloading",
          slideId: slideData.id,
          pages: slideData.page_count || 0,
        }),
      );
      dispatch(closeUploadModal());
      intentRef.current = null;
      setTitle("");
      setFile(null);
    } catch (err: any) {
      const details = err.response?.data;
      const message = typeof details?.error === "string" ? details.error
        : typeof details?.detail === "string" ? details.detail
        : details && typeof details === "object" ? Object.values(details).flat().join(" ")
        : "Upload failed. Please try again.";
      dispatch(updateProgress({ id: uploadId, progress: 0, status: "error", error: message }));
      setErrorMsg(message);
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    if (submitting) return;
    intentRef.current = null;
    dispatch(closeUploadModal());
    setTitle("");
    setFile(null);
    setErrorMsg("");
    setSelectedSubject(null);
    setSelectedBlock(null);
    setSelectedSubBlock(null);
    setSelectedTopic(null);
    setCustomTopicName("");
  }

  const subject = selectedSubject
    ? curriculum.find((s) => s.id === selectedSubject)
    : null;
  const blocks = subject?.blocks || [];
  const block = selectedBlock
    ? blocks.find((b) => b.id === selectedBlock)
    : null;
  const subBlocks = block?.subBlocks || [];
  const subBlock = selectedSubBlock
    ? subBlocks.find((t) => t.id === selectedSubBlock)
    : null;

  // Topics can come from either the sub-block or directly from the block
  const topics = subBlock?.topics || block?.topics || [];

  return (
    <AnimatePresence>
      {isModalOpen && (
        <motion.div
          className="fixed inset-0 z-50 flex items-end justify-center sm:items-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={reset}
          />

          <motion.div
            className="relative z-10 w-full max-w-md rounded-t-3xl border border-border bg-card p-6 shadow-2xl sm:rounded-3xl"
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
            transition={{ type: "spring", stiffness: 320, damping: 28 }}
          >
            <div className="mb-5 flex items-center justify-between">
              <div>
                <p className="text-[10px] font-medium uppercase tracking-widest text-primary">
                  {canUpload
                    ? isVerifiedClassHead
                      ? "Class Head · Upload"
                      : "Uploader · Upload"
                    : "Restricted"}
                </p>
                <h2 className="mt-0.5 font-serif text-xl">Upload Slides</h2>
                {subject && (
                  <p className="mt-0.5 text-[11px] text-muted-foreground">
                    {subject.title}
                    {block && ` · ${block.title}`}
                    {selectedSubBlock &&
                      subBlocks.find((t) => t.id === selectedSubBlock) &&
                      ` · ${subBlocks.find((t) => t.id === selectedSubBlock)?.title}`}
                    {selectedTopic &&
                      topics.find((s) => s.id === selectedTopic) &&
                      ` · ${topics.find((s) => s.id === selectedTopic)?.title}`}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={reset}
                className="flex size-8 items-center justify-center rounded-full border border-border text-muted-foreground transition-colors hover:text-foreground"
                aria-label="Close"
              >
                <FontAwesomeIcon icon={faXmark} className="size-4" />
              </button>
            </div>

            {!canUpload ? (
              /* ── Locked state for regular students ── */
              <div className="flex flex-col items-center gap-4 rounded-2xl border border-border bg-background/60 py-10 text-center">
                <span className="flex size-14 items-center justify-center rounded-full bg-muted text-muted-foreground">
                  <FontAwesomeIcon icon={faLock} className="size-6" />
                </span>
                <div>
                  <p className="font-serif text-lg">
                    Only uploaders can add files
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Ask your class rep to upload the slides or past questions,
                    or to grant you upload access.
                  </p>
                </div>
              </div>
            ) : loadingCurriculum ? (
              /* ── Loading curriculum ── */
              <div className="flex flex-col items-center gap-4 rounded-2xl border border-border bg-background/60 py-10 text-center">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
                <p className="text-sm text-muted-foreground">
                  Loading courses...
                </p>
              </div>
            ) : errorMsg && curriculum.length === 0 ? (
              /* ── Error state ── */
              <div className="flex flex-col items-center gap-4 rounded-2xl border border-destructive/20 bg-destructive/5 py-10 text-center">
                <span className="flex size-14 items-center justify-center rounded-full bg-destructive/10 text-destructive">
                  <FontAwesomeIcon icon={faTriangleExclamation} className="size-6" />
                </span>
                <div className="space-y-1">
                  <p role="alert" className="font-semibold text-destructive">{errorMsg}</p>
                </div>
              </div>
            ) : curriculum.length === 0 ? (
              /* ── No curriculum ── */
              <div className="flex flex-col items-center gap-4 rounded-2xl border border-border bg-background/60 py-10 text-center">
                <p className="text-sm text-muted-foreground">
                  No courses available. Please contact admin.
                </p>
              </div>
            ) : (
              <form onSubmit={handleSubmit}>
                <fieldset disabled={submitting} className="space-y-4">
                {/* Subject Selection */}
                <div>
                  <label className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
                    Subject
                  </label>
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
                          setCustomTopicName("");
                        }}
                        className={`rounded-xl border px-3 py-2 text-sm transition-colors ${
                          selectedSubject === subj.id
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-border bg-background hover:border-primary/50"
                        }`}
                      >
                        {subj.title}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Block Selection */}
                {selectedSubject && blocks.length > 0 && (
                  <div>
                    <label className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
                      Block
                    </label>
                    <div className="mt-1.5 grid grid-cols-2 gap-2">
                      {blocks.map((blk) => (
                        <button
                          key={blk.id}
                          type="button"
                          onClick={() => {
                            setSelectedBlock(blk.id);
                            setSelectedSubBlock(null);
                            setSelectedTopic(null);
                            setCustomTopicName("");
                          }}
                          className={`rounded-xl border px-3 py-2 text-sm transition-colors ${
                            selectedBlock === blk.id
                              ? "border-primary bg-primary text-primary-foreground"
                              : "border-border bg-background hover:border-primary/50"
                          }`}
                        >
                          {blk.title}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Sub-Block Selection */}
                {selectedBlock && subBlocks.length > 0 && (
                  <div>
                    <label className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
                      Sub-Block{" "}
                      <span className="text-[9px] text-muted-foreground/60">
                        (Optional)
                      </span>
                    </label>
                    <div className="mt-1.5 grid grid-cols-2 gap-2">
                      {subBlocks.map((subBlk) => (
                        <button
                          key={subBlk.id}
                          type="button"
                          onClick={() => {
                            setSelectedSubBlock(subBlk.id);
                            setSelectedTopic(null);
                            setCustomTopicName("");
                          }}
                          className={`rounded-xl border px-3 py-2 text-sm transition-colors ${
                            selectedSubBlock === subBlk.id
                              ? "border-primary bg-primary text-primary-foreground"
                              : "border-border bg-background hover:border-primary/50"
                          }`}
                        >
                          {subBlk.title}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Topic Selection */}
                {selectedBlock && (
                  <div className="space-y-3">
                    {topics.length > 0 && (
                      <div>
                        <label className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
                          Select Existing Topic
                        </label>
                        <div className="mt-1.5 grid grid-cols-2 gap-2">
                          {topics.map((topic) => (
                            <button
                              key={topic.id}
                              type="button"
                              onClick={() => {
                                setSelectedTopic(topic.id);
                                setCustomTopicName("");
                              }}
                              className={`rounded-xl border px-3 py-2 text-sm truncate transition-colors ${
                                selectedTopic === topic.id
                                  ? "border-primary bg-primary text-primary-foreground"
                                  : "border-border bg-background hover:border-primary/50"
                              }`}
                            >
                              {topic.title}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                    {isVerifiedClassHead && <div>
                      <label className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
                        {topics.length > 0 ? "Or Enter New Topic Name" : "Topic Name (Optional)"}
                      </label>
                      <input
                        type="text"
                        placeholder="e.g. Upper Limb"
                        value={customTopicName}
                        onChange={(e) => {
                          setCustomTopicName(e.target.value);
                          setSelectedTopic(null);
                        }}
                        className="mt-1.5 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary"
                      />
                    </div>}
                  </div>
                )}

                {/* Drop zone */}
                {selectedSubject && selectedBlock && (
                  <>
                    <div
                      className={`relative flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed p-8 transition-colors ${
                        dragging
                          ? "border-primary bg-primary/5"
                          : "border-border hover:border-primary/50"
                      }`}
                      onClick={() => inputRef.current?.click()}
                      onDragOver={(e) => {
                        e.preventDefault();
                        setDragging(true);
                      }}
                      onDragLeave={() => setDragging(false)}
                      onDrop={handleDrop}
                    >
                      <input
                        ref={inputRef}
                        type="file"
                        accept=".pdf,.ppt,.pptx,.docx"
                        className="sr-only"
                        onChange={(e) =>
                          e.target.files?.[0] && handleFile(e.target.files[0])
                        }
                      />
                      {file ? (
                        <>
                          <FontAwesomeIcon
                            icon={faFileLines}
                            className="size-8 text-primary"
                          />
                          <p className="text-center text-sm font-medium">
                            {file.name}
                          </p>
                          <p className="text-[11px] text-muted-foreground">
                            {(file.size / 1024 / 1024).toFixed(1)} MB · click to
                            change
                          </p>
                        </>
                      ) : (
                        <>
                          <FontAwesomeIcon
                            icon={faCloudArrowUp}
                            className="size-8 text-muted-foreground"
                          />
                          <p className="text-center text-sm text-muted-foreground">
                            Drop PDF, PPT, PPTX or DOCX here
                            <br />
                            <span className="text-primary">
                              or click to browse
                            </span>
                          </p>
                        </>
                      )}
                    </div>

                    {errorMsg && (
                      <p role="alert" className="flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] text-destructive">
                        <FontAwesomeIcon
                          icon={faTriangleExclamation}
                          className="size-3.5 shrink-0"
                        />
                        {errorMsg}
                      </p>
                    )}

                    {/* Title */}
                    <div>
                      <label
                        className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground"
                        htmlFor="slide-title"
                      >
                        Title
                      </label>
                      <input
                        id="slide-title"
                        type="text"
                        maxLength={200}
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder="e.g. Axilla: Boundaries & Contents"
                        className="mt-1.5 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition-colors placeholder:text-muted-foreground/60 focus:border-primary"
                      />
                    </div>

                    <motion.button
                      type="submit"
                      disabled={submitting || !file || !title.trim()}
                      whileTap={{ scale: 0.97 }}
                      className="h-11 w-full rounded-full bg-primary text-sm font-medium text-primary-foreground transition-opacity disabled:opacity-40"
                    >
                      {submitting ? "Saving upload..." : "Upload slides"}
                    </motion.button>
                  </>
                )}
                </fieldset>
              </form>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
