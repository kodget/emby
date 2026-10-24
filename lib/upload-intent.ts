export type UploadIntent = { file: File; metadata: string; requestId: string };

// Keep the same identity after a lost response; an edited form is a new intent.
export function uploadIntent(previous: UploadIntent | null, file: File, metadata: string): UploadIntent {
  if (previous?.file === file && previous.metadata === metadata) return previous;
  return { file, metadata, requestId: crypto.randomUUID() };
}

export function uploadOwner(): string {
  try {
    const user = JSON.parse(sessionStorage.getItem("user") || "{}");
    return JSON.stringify([user.user_id ?? user.id, user.class_group_id ?? user.class_group]);
  } catch {
    return "";
  }
}
