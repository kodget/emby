"use client"

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { classApi, authApi } from "@/lib/api";
import { UserProfile } from "@/lib/api";
import AuthGuard from "@/components/auth/auth-guard";
import { isClassHead } from "@/lib/guards";
import {
  Users,
  School,
  Hash,
  Crown,
  Calendar,
  Plus,
  FileText,
  BookOpen,
} from "lucide-react";
import { useState } from "react";

export default function ClassPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [classData, setClassData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const profileData = await authApi.getProfile();
      setProfile(profileData);

      if (profileData.class_group) {
        const classInfo = await classApi.getMyClass();
        setClassData(classInfo);
      }
    } catch (error) {
      console.error("Failed to load data:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [])
};