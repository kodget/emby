"use client";

import { motion } from "framer-motion";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faCloudArrowUp } from "@fortawesome/free-solid-svg-icons";
import { useAppDispatch, useCanUpload } from "@/store/hooks";
import { openUploadModal } from "@/store/uploads-slice";

export function ModuleUploadButton({
  courseId,
  moduleId,
}: {
  courseId: string;
  moduleId: string;
}) {
  const dispatch = useAppDispatch();
  const canUpload = useCanUpload();

  if (!canUpload) return null;

  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.93 }}
      onClick={() => dispatch(openUploadModal({ courseId, moduleId }))}
      className="inline-flex items-center gap-1.5 rounded-full border border-dashed border-primary/50 bg-primary/5 px-3 py-1.5 text-[12px] font-medium text-primary hover:bg-primary/10 transition-colors"
    >
      <FontAwesomeIcon icon={faCloudArrowUp} className="size-3" />
      Upload slides / past questions (Class Rep Only)
    </motion.button>
  );
}
