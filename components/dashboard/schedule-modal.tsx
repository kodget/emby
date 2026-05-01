// components/dashboard/schedule-modal.tsx
"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faXmark,
  faCalendar,
  faClock,
  faBook,
  faListCheck,
  faClone,
  faTrophy,
} from "@fortawesome/free-solid-svg-icons";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
  closeScheduleModal,
  addScheduleItem,
  updateScheduleItem,
  type ScheduleItem,
  type ScheduleItemType,
} from "@/store/schedule-slice";
import { curriculum } from "@/lib/curriculum";
import { getSlidesForCourse } from "@/lib/slides";

const typeIcons = {
  read: faBook,
  quiz: faListCheck,
  flashcards: faClone,
  steeplechase: faTrophy,
};

const typeLabels = {
  read: "Read Slides",
  quiz: "Take Quiz",
  flashcards: "Review Flashcards",
  steeplechase: "Steeplechase Practice",
};

export function ScheduleModal() {
  const dispatch = useAppDispatch();
  const { isModalOpen, editingItem } = useAppSelector((s) => s.schedule);

  const [type, setType] = useState<ScheduleItemType>("read");
  const [title, setTitle] = useState("");
  const [courseId, setCourseName] = useState("");
  const [courseName, setSelectedCourse] = useState("");
  const [slideId, setSlideId] = useState("");
  const [detail, setDetail] = useState("");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [minutes, setMinutes] = useState(30);
  const [notes, setNotes] = useState("");

  // Initialize with editing item or defaults
  useEffect(() => {
    if (editingItem) {
      setType(editingItem.type);
      setTitle(editingItem.title);
      setCourseName(editingItem.courseId);
      setSelectedCourse(editingItem.courseName);
      setSlideId(editingItem.slideId || "");
      setDetail(editingItem.details || "");
      setDate(editingItem.scheduledDate);
      setTime(editingItem.scheduledTime || "");
      setMinutes(editingItem.estimatedMinutes);
      setNotes(editingItem.notes || "");
    } else {
      const today = new Date().toISOString().split("T")[0];
      setDate(today);
      setTime("09:00");
    }
  }, [editingItem, isModalOpen]);

  // Get all courses from curriculum
  const allCourses = curriculum.flatMap((subject) =>
    subject.blocks.flatMap((block) =>
      block.topics.length > 0
        ? block.topics.map((topic) => ({
            id: topic.id,
            name: topic.title,
            subject: subject.title,
          }))
        : [{ id: block.id, name: block.title, subject: subject.title }],
    ),
  );

  // Get slides for selected course
  const availableSlides = courseId ? getSlidesForCourse(courseId) : [];

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!title.trim() || !courseId || !date) return;

    const item: ScheduleItem = {
      id: editingItem?.id || `sched-${Date.now()}`,
      type,
      title: title.trim(),
      courseId,
      courseName,
      slideId: type === "read" ? slideId : undefined,
      topicId: type !== "read" ? courseId : undefined,
      details: detail.trim() || undefined,
      estimatedMinutes: minutes,
      scheduledDate: date,
      scheduledTime: time || undefined,
      completed: editingItem?.completed || false,
      completedAt: editingItem?.completedAt,
      notes: notes.trim() || undefined,
    };

    if (editingItem) {
      dispatch(updateScheduleItem(item));
    } else {
      dispatch(addScheduleItem(item));
    }

    handleClose();
  }

  function handleClose() {
    dispatch(closeScheduleModal());
    // Reset form
    setType("read");
    setTitle("");
    setCourseName("");
    setSelectedCourse("");
    setSlideId("");
    setDate("");
    setTime("");
    setMinutes(30);
    setNotes("");
  }

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
            onClick={handleClose}
          />

          <motion.div
            className="relative z-10 w-full max-w-2xl rounded-t-3xl border border-border bg-card p-6 shadow-2xl sm:rounded-3xl max-h-[90vh] overflow-y-auto"
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
            transition={{ type: "spring", stiffness: 320, damping: 28 }}
          >
            <div className="mb-5 flex items-center justify-between">
              <div>
                <p className="text-[10px] font-medium uppercase tracking-widest text-primary">
                  Study Schedule
                </p>
                <h2 className="mt-0.5 font-serif text-xl">
                  {editingItem ? "Edit Schedule" : "Add to Schedule"}
                </h2>
              </div>
              <button
                type="button"
                onClick={handleClose}
                className="flex size-8 items-center justify-center rounded-full border border-border text-muted-foreground transition-colors hover:text-foreground"
                aria-label="Close"
              >
                <FontAwesomeIcon icon={faXmark} className="size-4" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Activity Type */}
              <div>
                <label className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
                  Activity Type
                </label>
                <div className="mt-1.5 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {(Object.keys(typeIcons) as ScheduleItemType[]).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setType(t)}
                      className={`flex flex-col items-center gap-2 rounded-xl border p-3 transition-colors ${
                        type === t
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border bg-background hover:border-primary/50"
                      }`}
                    >
                      <FontAwesomeIcon icon={typeIcons[t]} className="size-5" />
                      <span className="text-xs font-medium">
                        {typeLabels[t]}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Title */}
              <div>
                <label
                  className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground"
                  htmlFor="title"
                >
                  Title
                </label>
                <input
                  id="title"
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Read Axilla boundaries"
                  className="mt-1.5 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition-colors placeholder:text-muted-foreground/60 focus:border-primary"
                  required
                />
              </div>

              {/* Course Selection */}
              <div>
                <label
                  className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground"
                  htmlFor="course"
                >
                  Course
                </label>
                <select
                  id="course"
                  value={courseId}
                  onChange={(e) => {
                    setCourseName(e.target.value);
                    const selected = allCourses.find(
                      (c) => c.id === e.target.value,
                    );
                    setSelectedCourse(selected?.name || "");
                    setSlideId(""); // Reset slide selection
                  }}
                  className="mt-1.5 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition-colors focus:border-primary"
                  required
                >
                  <option value="">Select a course</option>
                  {allCourses.map((course) => (
                    <option key={course.id} value={course.id}>
                      {course.subject} · {course.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Slide Selection (only for read type) */}
              {type === "read" && courseId && availableSlides.length > 0 && (
                <div>
                  <label
                    className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground"
                    htmlFor="slide"
                  >
                    Slide (Optional)
                  </label>
                  <select
                    id="slide"
                    value={slideId}
                    onChange={(e) => setSlideId(e.target.value)}
                    className="mt-1.5 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition-colors focus:border-primary"
                  >
                    <option value="">Any slide</option>
                    {availableSlides.map((slide) => (
                      <option key={slide.id} value={slide.id}>
                        {slide.title} ({slide.pages} pages)
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Activity Details */}
              <div>
                <label
                  className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground"
                  htmlFor="detail"
                >
                  {typeLabels[type]} details
                </label>
                <input
                  id="detail"
                  type="text"
                  value={detail}
                  onChange={(e) => setDetail(e.target.value)}
                  placeholder={
                    type === "read"
                      ? "e.g. Section 1, slides 1-5"
                      : type === "quiz"
                        ? "e.g. 10 questions"
                        : type === "flashcards"
                          ? "e.g. 15 cards due"
                          : "e.g. 5 stations"
                  }
                  className="mt-1.5 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition-colors placeholder:text-muted-foreground/60 focus:border-primary"
                />
                <p className="mt-2 text-xs text-muted-foreground">
                  {type === "read"
                    ? "Choose a slide, page range, or section to focus your reading session."
                    : type === "quiz"
                      ? "Describe the quiz length or topic focus."
                      : type === "flashcards"
                        ? "Add how many cards or which deck to review."
                        : "Describe the steeplechase practice format."}
                </p>
              </div>

              {/* Date and Time */}
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label
                    className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground"
                    htmlFor="date"
                  >
                    Date
                  </label>
                  <div className="relative mt-1.5">
                    <input
                      id="date"
                      type="date"
                      value={date}
                      onChange={(e) => setDate(e.target.value)}
                      className="w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition-colors focus:border-primary"
                      required
                    />
                    <FontAwesomeIcon
                      icon={faCalendar}
                      className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
                    />
                  </div>
                </div>

                <div>
                  <label
                    className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground"
                    htmlFor="time"
                  >
                    Time (Optional)
                  </label>
                  <div className="relative mt-1.5">
                    <input
                      id="time"
                      type="time"
                      value={time}
                      onChange={(e) => setTime(e.target.value)}
                      className="w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition-colors focus:border-primary"
                    />
                    <FontAwesomeIcon
                      icon={faClock}
                      className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
                    />
                  </div>
                </div>
              </div>

              {/* Estimated Minutes */}
              <div>
                <label
                  className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground"
                  htmlFor="minutes"
                >
                  Estimated Time: {minutes} minutes
                </label>
                <input
                  id="minutes"
                  type="range"
                  min="5"
                  max="120"
                  step="5"
                  value={minutes}
                  onChange={(e) => setMinutes(Number(e.target.value))}
                  className="mt-1.5 w-full"
                />
                <div className="mt-1 flex justify-between text-xs text-muted-foreground">
                  <span>5 min</span>
                  <span>120 min</span>
                </div>
              </div>

              {/* Notes */}
              <div>
                <label
                  className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground"
                  htmlFor="notes"
                >
                  Notes (Optional)
                </label>
                <textarea
                  id="notes"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Add any notes or reminders..."
                  rows={3}
                  className="mt-1.5 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm outline-none transition-colors placeholder:text-muted-foreground/60 focus:border-primary resize-none"
                />
              </div>

              {/* Submit Button */}
              <motion.button
                type="submit"
                whileTap={{ scale: 0.97 }}
                className="h-11 w-full rounded-full bg-primary text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
              >
                {editingItem ? "Update Schedule" : "Add to Schedule"}
              </motion.button>
            </form>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
