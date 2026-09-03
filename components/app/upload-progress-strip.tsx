"use client"

import { AnimatePresence, motion } from "framer-motion"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { faCircleCheck, faSpinner } from "@fortawesome/free-solid-svg-icons"
import { useAppSelector, useAppDispatch } from "@/store/hooks"
import { updateProgress, type UploadStatus } from "@/store/uploads-slice"
import { useEffect } from "react"

export function UploadProgressStrip() {
  const dispatch = useAppDispatch()
  const uploads = useAppSelector((s) => s.uploads.items.filter((u) => u.status !== "done" && u.status !== "error"))
  const recent = useAppSelector((s) =>
    s.uploads.items.filter((u) => u.status === "done" || u.status === "error").slice(0, 1)
  )
  const visible = [...uploads, ...recent].slice(0, 1)

  useEffect(() => {
    const activeUploads = uploads.filter((u) => u.slideId && u.status !== "uploading" && u.status !== "done" && u.status !== "error");
    if (activeUploads.length === 0) return;

    const interval = setInterval(() => {
      activeUploads.forEach(async (u) => {
        try {
          const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/api/slides/${u.slideId}/status/`, {
            headers: {
              Authorization: `Bearer ${sessionStorage.getItem("token")}`,
            },
          });
          if (res.ok) {
            const data = await res.json();
            let progress = u.progress;
            let status: UploadStatus = "processing";
            if (data.status === "downloading") {
              progress = 60;
              status = "downloading";
            } else if (data.status === "extracting_text") {
              progress = 70;
              status = "extracting_text";
            } else if (data.status === "converting_to_jpg") {
              progress = 80;
              status = "converting_to_jpg";
            } else if (data.status === "generating_quizzes") {
              progress = 90;
              status = "generating_quizzes";
            } else if (data.status === "completed") {
              progress = 100;
              status = "done";
            } else if (data.status === "failed") {
              progress = 0;
              status = "error";
            }

            if (status !== u.status || progress !== u.progress) {
              dispatch(updateProgress({ id: u.id, progress, status }));
            }
          }
        } catch (e) {
          // Ignore polling errors
        }
      });
    }, 3000);

    return () => clearInterval(interval);
  }, [uploads, dispatch]);

  const getStatusText = (status: UploadStatus, progress: number) => {
    if (status === "done") return "Done"
    if (status === "error") return "Failed"
    if (status === "uploading") return "Uploading..."
    if (status === "downloading") return "Downloading..."
    if (status === "extracting_text") return "Extracting text..."
    if (status === "converting_to_jpg") return "Converting pages..."
    if (status === "generating_quizzes") return "Generating quizzes..."
    return "Processing..."
  }

  return (
    <AnimatePresence>
      {visible.map((u) => (
        <motion.div
          key={u.id}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
          className="mx-3 mb-3 rounded-xl border border-border bg-background px-3 py-2.5"
        >
          <div className="flex items-center gap-2 text-[12px]">
            {u.status === "done" ? (
              <FontAwesomeIcon icon={faCircleCheck} className="size-3.5 text-primary shrink-0" />
            ) : (
              <FontAwesomeIcon icon={faSpinner} className="size-3.5 text-muted-foreground shrink-0 animate-spin" />
            )}
            <span className="truncate text-muted-foreground">{u.title}</span>
            <span className="ml-auto shrink-0 font-medium text-foreground">
              {getStatusText(u.status, u.progress)}
            </span>
          </div>
          {u.status !== "done" && (
            <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-muted">
              <motion.div
                className="h-full rounded-full bg-primary"
                animate={{ width: `${u.progress}%` }}
                transition={{ ease: "easeOut", duration: 0.2 }}
              />
            </div>
          )}
        </motion.div>
      ))}
    </AnimatePresence>
  )
}
