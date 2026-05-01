"use client"

import { AnimatePresence, motion } from "framer-motion"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import { faCircleCheck, faSpinner } from "@fortawesome/free-solid-svg-icons"
import { useAppSelector } from "@/store/hooks"

export function UploadProgressStrip() {
  const uploads = useAppSelector((s) => s.uploads.items.filter((u) => u.status !== "done"))
  const recent = useAppSelector((s) =>
    s.uploads.items.filter((u) => u.status === "done").slice(0, 1)
  )
  const visible = [...uploads, ...recent].slice(0, 1)

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
              {u.status === "done" ? "Done" : `${u.progress}%`}
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
