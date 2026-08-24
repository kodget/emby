"use client";

import { useRef, useState, useCallback, useEffect } from "react";
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
  const inputRef = useRef<HTMLInputElement>(null);

  // Hierarchical selection state
  const [selectedSubject, setSelectedSubject] = useState<SubjectId | null>(
    null,
  );
  const [selectedBlock, setSelectedBlock] = useState<BlockId | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<TopicId | null>(null);
  const [selectedSection, setSelectedSection] = useState<string | null>(null);
  const [customSectionName, setCustomSectionName] = useState("");

  // Load curriculum from API
  useEffect(() => {
    if (isModalOpen) {
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
      const allowed = [
        "application/pdf",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
      ];
      if (!allowed.includes(f.type) && !f.name.match(/\.(pdf|ppt|pptx)$/i)) {
        setErrorMsg("Only PDF or PowerPoint files are supported.");
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
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !title.trim() || !selectedSubject || !selectedBlock) return;

    const uploadId = `upload-${Date.now()}`;

    dispatch(
      addUpload({
        id: uploadId,
        courseId: selectedTopic || selectedBlock,
        moduleId: selectedTopic || selectedBlock,
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
    const apiBase =
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    dispatch(closeUploadModal());

    try {
      // Send the raw file directly to Django — it processes, converts to JPGs,
      // uploads to Cloudinary, and returns the finished Slide record.
      // This avoids the frontend→Cloudinary→backend download 401 problem.
      let sectionId = selectedSection;

      if (customSectionName.trim()) {
        const createSecResponse = await fetch(`${apiBase}/api/topics/`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${sessionStorage.getItem("token")}`,
          },
          body: JSON.stringify({
            name: customSectionName.trim(),
            sub_block: selectedTopic,
            topic: selectedTopic,
            block: selectedBlock,
          }),
        });
        if (createSecResponse.ok) {
          const newSec = await createSecResponse.json();
          sectionId = newSec.id;
        } else {
          const errorData = await createSecResponse.json().catch(() => ({}));
          throw new Error(errorData.error || "Failed to create new topic");
        }
      }

      const formData = new FormData();
      formData.append("file", file);
      formData.append("title", title.trim());
      formData.append("subject", selectedSubject);
      formData.append("block", selectedBlock);
      if (selectedTopic) formData.append("sub_block", selectedTopic);
      if (selectedTopic) formData.append("topic", selectedTopic);
      if (sectionId) formData.append("topic", sectionId);
      if (sectionId) formData.append("section", sectionId);

      dispatch(
        updateProgress({ id: uploadId, progress: 30, status: "uploading" }),
      );

      const response = await fetch(
        `${apiBase}/api/slides/upload_and_process/`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${sessionStorage.getItem("token")}`,
          },
          body: formData,
        },
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || "Upload failed");
      }

      const slideData = await response.json();

      dispatch(
        updateProgress({
          id: uploadId,
          progress: 100,
          status: "done",
          pages: slideData.page_count || 0,
        }),
      );
    } catch (err: any) {
      console.error(err);
      dispatch(updateProgress({ id: uploadId, progress: 0, status: "error" }));
      setErrorMsg(err.message || "Upload failed. Please try again.");
    }

    setTitle("");
    setFile(null);
  }

  function reset() {
    dispatch(closeUploadModal());
    setTitle("");
    setFile(null);
    setErrorMsg("");
    setSelectedSubject(null);
    setSelectedBlock(null);
    setSelectedTopic(null);
    setSelectedSection(null);
    setCustomSectionName("");
  }

  const subject = selectedSubject
    ? curriculum.find((s) => s.id === selectedSubject)
    : null;
  const blocks = subject?.blocks || [];
  const block = selectedBlock
    ? blocks.find((b) => b.id === selectedBlock)
    : null;
  const topics = block?.topics || [];
  const topic = selectedTopic
    ? topics.find((t) => t.id === selectedTopic)
    : null;

  // Sections can come from either the topic or directly from the block
  const sections = topic?.sections || block?.sections || [];

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
                    {selectedTopic &&
                      topics.find((t) => t.id === selectedTopic) &&
                      ` · ${topics.find((t) => t.id === selectedTopic)?.title}`}
                    {selectedSection &&
                      sections.find((s) => s.id === selectedSection) &&
                      ` · ${sections.find((s) => s.id === selectedSection)?.title}`}
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
            ) : errorMsg ? (
              /* ── Error state ── */
              <div className="flex flex-col items-center gap-4 rounded-2xl border border-destructive/20 bg-destructive/5 py-10 text-center">
                <span className="flex size-14 items-center justify-center rounded-full bg-destructive/10 text-destructive">
                  <FontAwesomeIcon icon={faTriangleExclamation} className="size-6" />
                </span>
                <div className="space-y-1">
                  <p className="font-semibold text-destructive">{errorMsg}</p>
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
              <form onSubmit={handleSubmit} className="space-y-4">
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
                          setSelectedTopic(null);
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
                            setSelectedTopic(null);
                            setSelectedSection(null);
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

                {/* Topic Selection (sub-blocks) */}
                {selectedBlock && topics.length > 0 && (
                  <div>
                    <label className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
                      Topic{" "}
                      <span className="text-[9px] text-muted-foreground/60">
                        (Optional)
                      </span>
                    </label>
                    <div className="mt-1.5 grid grid-cols-2 gap-2">
                      {topics.map((topic) => (
                        <button
                          key={topic.id}
                          type="button"
                          onClick={() => {
                            setSelectedTopic(topic.id);
                            setSelectedSection(null);
                          }}
                          className={`rounded-xl border px-3 py-2 text-sm transition-colors ${
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

                {/* Section Selection (subsections) */}
                {selectedBlock && (
                  <div className="space-y-3">
                    {sections.length > 0 && (
                      <div>
                        <label className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
                          Select Existing Topic
                        </label>
                        <div className="mt-1.5 grid grid-cols-2 gap-2">
                          {sections.map((section) => (
                            <button
                              key={section.id}
                              type="button"
                              onClick={() => {
                                setSelectedSection(section.id);
                                setCustomSectionName("");
                              }}
                              className={`rounded-xl border px-3 py-2 text-sm truncate transition-colors ${
                                selectedSection === section.id
                                  ? "border-primary bg-primary text-primary-foreground"
                                  : "border-border bg-background hover:border-primary/50"
                              }`}
                            >
                              {section.title}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                    <div>
                      <label className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
                        {sections.length > 0 ? "Or Enter New Topic Name" : "Topic Name (Optional)"}
                      </label>
                      <input
                        type="text"
                        placeholder="e.g. Upper Limb"
                        value={customSectionName}
                        onChange={(e) => {
                          setCustomSectionName(e.target.value);
                          setSelectedSection(null);
                        }}
                        className="mt-1.5 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary"
                      />
                    </div>
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
                        accept=".pdf,.ppt,.pptx"
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
                            Drop PDF or PowerPoint here
                            <br />
                            <span className="text-primary">
                              or click to browse
                            </span>
                          </p>
                        </>
                      )}
                    </div>

                    {errorMsg && (
                      <p className="flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] text-destructive">
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
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder="e.g. Axilla: Boundaries & Contents"
                        className="mt-1.5 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition-colors placeholder:text-muted-foreground/60 focus:border-primary"
                      />
                    </div>

                    <motion.button
                      type="submit"
                      disabled={!file || !title.trim()}
                      whileTap={{ scale: 0.97 }}
                      className="h-11 w-full rounded-full bg-primary text-sm font-medium text-primary-foreground transition-opacity disabled:opacity-40"
                    >
                      Upload slides
                    </motion.button>
                  </>
                )}
              </form>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
