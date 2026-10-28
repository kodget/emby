import { useDispatch, useSelector } from "react-redux";
import { useSyncExternalStore } from "react";
import type { RootState, AppDispatch } from "./store";

export const useAppDispatch = () => useDispatch<AppDispatch>();
export const useAppSelector = <T>(selector: (state: RootState) => T) =>
  useSelector(selector);

const subscribeToHydration = () => () => {};
const clientSnapshot = () => true;
const serverSnapshot = () => false;

/** Returns true if the current user can upload slides/past questions (uploader role or class representative) */
export function useCanUpload(): boolean {
  const hydrated = useSyncExternalStore(subscribeToHydration, clientSnapshot, serverSnapshot);
  const allowed = useAppSelector(
    (s) => s.user.role === "uploader" || (s.user.role === "class-rep" && s.user.isVerifiedClassHead),
  );
  // A parent can restore the session before streamed children hydrate. Their
  // first render must still match the server's permission-free placeholder.
  return hydrated && allowed;
}

/** Returns true if the current user is the verified class head */
export function useIsVerifiedClassHead(): boolean {
  return useAppSelector((s) => s.user.isVerifiedClassHead);
}

export const useIsClassRep = () =>
  useAppSelector((s) => s.user.role === "class-rep");

/** Reset content views when the signed-in account or class privileges change. */
export const useContentSessionKey = () => useAppSelector((s) => JSON.stringify([
  s.user.id, s.user.school, s.user.setName, s.user.isSignedIn,
  s.user.role, s.user.isVerifiedClassHead,
]));
