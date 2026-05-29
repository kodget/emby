import { useGoogleLogin } from "@react-oauth/google";
import type { CredentialResponse } from "@react-oauth/google";
import { useDispatch, useSelector } from "react-redux";
import { useCallback, useEffect } from "react";
import axios from "axios";
import type { RootState } from "@/store/store";
import { updateUserProfile, logout } from "@/store/user-slice";
import type { UserRole } from "@/store/user-slice";
import { statsApi } from "@/lib/api";

type BackendUser = {
  id: string;
  name: string;
  email: string;
  photo_url: string | null;
  role: UserRole;
  is_class_rep: boolean;
  streak?: number;
  subscription: any;
};

export function useAuth() {
  const dispatch = useDispatch();
  const user = useSelector((state: RootState) => state.user);

  const login = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      try {
        const res = await axios.post<{ token: string; user: BackendUser }>(
          "http://localhost:8000/auth/google-login/",
          {
            token: tokenResponse.access_token,
          },
        );

        const backendUser = res.data.user;

        // Store token and user data
        sessionStorage.setItem("token", res.data.token);
        sessionStorage.setItem("user", JSON.stringify(backendUser));
        axios.defaults.headers.common["Authorization"] =
          `Bearer ${res.data.token}`;

        // Fetch user stats
        let stats = null;
        try {
          stats = await statsApi.getMyStats();
        } catch (error) {
          console.log("Stats not available yet:", error);
        }

        dispatch(
          updateUserProfile({
            id: backendUser.id,
            name: backendUser.name,
            email: backendUser.email,
            photoUrl: backendUser.photo_url,
            role: backendUser.role,
            isClassRep: backendUser.is_class_rep,
            streak: stats?.current_streak || backendUser.streak || 0,
            points: stats?.points || 0,
            rank: stats?.rank || 0,
            school: stats?.school || "",
            setName: stats?.set_name || "",
            subscription: backendUser.subscription || {
              status: "free",
              tier: "free",
              expiresAt: null,
              paymentCardBrand: null,
              paymentLast4: null,
            },
          }),
        );
      } catch (error) {
        console.error("Google auth failed:", error);
      }
    },
    flow: "implicit",
  });

  const manualLogout = useCallback(() => {
    dispatch(logout());
    sessionStorage.removeItem("token");
    sessionStorage.removeItem("user");
    delete axios.defaults.headers.common["Authorization"];
  }, [dispatch]);

  useEffect(() => {
    const token = sessionStorage.getItem("token");
    const userStr = sessionStorage.getItem("user");
    if (token && userStr) {
      axios.defaults.headers.common["Authorization"] = `Bearer ${token}`;
      const backendUser: BackendUser = JSON.parse(userStr);

      // Immediately restore from storage so UI doesn't block
      dispatch(
        updateUserProfile({
          id: backendUser.id,
          name: backendUser.name,
          email: backendUser.email,
          photoUrl: backendUser.photo_url,
          role: backendUser.role,
          isClassRep: backendUser.is_class_rep,
          streak: backendUser.streak || 0,
          subscription: backendUser.subscription || {
            status: "free",
            tier: "free",
            expiresAt: null,
            paymentCardBrand: null,
            paymentLast4: null,
          },
        }),
      );

      // Refresh stats in background without blocking render
      statsApi
        .getMyStats()
        .then((stats) => {
          dispatch(
            updateUserProfile({
              id: backendUser.id,
              name: backendUser.name,
              email: backendUser.email,
              photoUrl: backendUser.photo_url,
              role: backendUser.role,
              isClassRep: backendUser.is_class_rep,
              streak: stats.current_streak,
              points: stats.points,
              rank: stats.rank,
              school: stats.school,
              setName: stats.set_name,
              subscription: backendUser.subscription || {
                status: "free",
                tier: "free",
                expiresAt: null,
                paymentCardBrand: null,
                paymentLast4: null,
              },
            }),
          );
        })
        .catch(() => {
          /* silently ignore, already using stored data */
        });
    }
  }, [dispatch]);

  return {
    login: () => login(),
    logout: manualLogout,
    user,
    isAuthenticated:
      typeof window !== "undefined" && !!sessionStorage.getItem("token"),
  };
}
