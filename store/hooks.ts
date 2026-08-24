import { useDispatch, useSelector } from "react-redux";
import type { RootState, AppDispatch } from "./store";

export const useAppDispatch = () => useDispatch<AppDispatch>();
export const useAppSelector = <T>(selector: (state: RootState) => T) =>
  useSelector(selector);

/** Returns true if the current user can upload slides/past questions (uploader role or class representative) */
export function useCanUpload(): boolean {
  return useAppSelector(
    (s) => s.user.role === "uploader" || s.user.role === "class-rep",
  );
}

/** Returns true if the current user is the verified class head */
export function useIsVerifiedClassHead(): boolean {
  return useAppSelector((s) => s.user.isVerifiedClassHead);
}

export const useIsClassRep = () =>
  useAppSelector((s) => s.user.role === "class-rep");
