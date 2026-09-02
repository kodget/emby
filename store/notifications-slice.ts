import { createSlice, PayloadAction, createAsyncThunk } from "@reduxjs/toolkit";
import api from "@/lib/api";

export interface Notification {
  id: string;
  type: string;
  priority: string;
  title: string;
  body: string;
  action_url: string;
  read: boolean;
  created_at: string;
}

export interface NotificationsState {
  items: Notification[];
  unreadCount: number;
  status: "idle" | "loading" | "succeeded" | "failed";
  error: string | null;
}

const initialState: NotificationsState = {
  items: [],
  unreadCount: 0,
  status: "idle",
  error: null,
};

export const fetchNotifications = createAsyncThunk(
  "notifications/fetchNotifications",
  async (unreadOnly?: boolean) => {
    const url = unreadOnly ? "/learning/notifications/?unread=true" : "/learning/notifications/";
    const response = await api.get(url);
    return response.data;
  }
);

export const markRead = createAsyncThunk(
  "notifications/markRead",
  async (id?: string) => {
    const payload = id ? { id } : {};
    const response = await api.post("/learning/notifications/read/", payload);
    return { id, marked_read: response.data.marked_read };
  }
);

const notificationsSlice = createSlice({
  name: "notifications",
  initialState,
  reducers: {
    addNotification: (state, action: PayloadAction<Notification>) => {
      state.items.unshift(action.payload);
      if (!action.payload.read) {
        state.unreadCount += 1;
      }
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchNotifications.pending, (state) => {
        state.status = "loading";
      })
      .addCase(fetchNotifications.fulfilled, (state, action) => {
        state.status = "succeeded";
        state.items = action.payload.results;
        state.unreadCount = action.payload.unread_count;
      })
      .addCase(fetchNotifications.rejected, (state, action) => {
        state.status = "failed";
        state.error = action.error.message || "Failed to fetch notifications";
      })
      .addCase(markRead.fulfilled, (state, action) => {
        if (action.payload.id) {
          const notification = state.items.find((n) => n.id === action.payload.id);
          if (notification && !notification.read) {
            notification.read = true;
            state.unreadCount = Math.max(0, state.unreadCount - 1);
          }
        } else {
          state.items.forEach((n) => (n.read = true));
          state.unreadCount = 0;
        }
      });
  },
});

export const { addNotification } = notificationsSlice.actions;

export default notificationsSlice.reducer;
