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
  class_role: string;
  class_head_verified: boolean;
  is_premium: boolean;
  subscription_tier: string;
  streak?: number;
};

export function useAuth() {
  const dispatch = useDispatch();
  const user = useSelector((state: RootState) => state.user);

  const login = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      try {
        const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const res = await axios.post<{ token: string; user: BackendUser }>(
          `${baseUrl}/auth/google-login/`,
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
            backendRole: backendUser.class_role,
            isVerifiedClassHead: backendUser.class_head_verified,
            streak: stats?.current_streak || backendUser.streak || 0,
            points: stats?.points || 0,
            rank: stats?.rank || 0,
            school: stats?.school || "",
            setName: stats?.set_name || "",
            subscription: {
              status: backendUser.is_premium ? "active" : "free",
              tier: backendUser.is_premium ? "premium" : "free",
              expiresAt: null,
              paymentCardBrand: null,
              paymentLast4: null,
            },
            usage: stats?.usage,
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
          backendRole: backendUser.class_role,
          isVerifiedClassHead: backendUser.class_head_verified,
          streak: backendUser.streak || 0,
          subscription: {
            status: backendUser.is_premium ? "active" : "free",
            tier: backendUser.is_premium ? "premium" : "free",
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
              backendRole: backendUser.class_role,
              isVerifiedClassHead: backendUser.class_head_verified,
              streak: stats.current_streak,
              points: stats.points,
              rank: stats.rank,
              school: stats.school,
              setName: stats.set_name,
              subscription: {
                status: backendUser.is_premium ? "active" : "free",
                tier: backendUser.is_premium ? "premium" : "free",
                expiresAt: null,
                paymentCardBrand: null,
                paymentLast4: null,
              },
              usage: stats.usage,
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
