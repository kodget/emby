import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

export type UploadStatus = "uploading" | "processing" | "done" | "error";

export type SlideUpload = {
  id: string;
  courseId: string;
  moduleId: string;
  // materialId this upload populates (generated on submit)
  materialId: string;
  title: string;
  fileName: string;
  pages: number;
  uploadedBy: string;
  uploadedAt: string;
  status: UploadStatus;
  progress: number;
  school: string;
  setName: string;
};

type UploadsState = {
  items: SlideUpload[];
  isModalOpen: boolean;
  targetCourseId: string | null;
  targetModuleId: string | null;
};

const initialState: UploadsState = {
  items: [],
  isModalOpen: false,
  targetCourseId: null,
  targetModuleId: null,
};

export const uploadsSlice = createSlice({
  name: "uploads",
  initialState,
  reducers: {
    openUploadModal(
      state,
      action: PayloadAction<{ courseId: string; moduleId: string }>,
    ) {
      state.isModalOpen = true;
      state.targetCourseId = action.payload.courseId;
      state.targetModuleId = action.payload.moduleId;
    },
    closeUploadModal(state) {
      state.isModalOpen = false;
      state.targetCourseId = null;
      state.targetModuleId = null;
    },
    addUpload(state, action: PayloadAction<SlideUpload>) {
      state.items.unshift(action.payload);
    },
    updateProgress(
      state,
      action: PayloadAction<{
        id: string;
        progress: number;
        status: UploadStatus;
        pages?: number;
      }>,
    ) {
      const item = state.items.find((u) => u.id === action.payload.id);
      if (item) {
        item.progress = action.payload.progress;
        item.status = action.payload.status;
        if (action.payload.pages !== undefined)
          item.pages = action.payload.pages;
      }
    },
  },
});

export const { openUploadModal, closeUploadModal, addUpload, updateProgress } =
  uploadsSlice.actions;
export default uploadsSlice.reducer;
