"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { curriculumApi, authApi } from "@/lib/api";
import { Slide, UserProfile } from "@/lib/api";
import AuthGuard from "@/components/auth/auth-guard";
import { canUploadMaterials } from "@/lib/guards";
import { FileText, Upload, Edit2, Trash2, Eye, Download } from "lucide-react";

export default function MaterialsPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [materials, setMaterials] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [profileData, materialsData] = await Promise.all([
        authApi.getProfile(),
        curriculumApi.getMaterials(),
      ]);
      setProfile(profileData);
      setMaterials(materialsData);
    } catch (error) {
      console.error("Failed to load data:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this material?")) return;
    try {
      await curriculumApi.deleteMaterial(id);
      await loadData();
    } catch (error) {
      console.error("Failed to delete material:", error);
      alert("Failed to delete material");
    }
  };

  const canManage = canUploadMaterials();

  if (loading) {
    return (
      <AuthGuard>
        <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-blue-50 flex items-center justify-center">
          <div className="text-center">
            <div className="w-16 h-16 border-4 border-purple-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-gray-600">Loading materials...</p>
          </div>
        </div>
      </AuthGuard>
    );
  }

  return (
    <AuthGuard>
      <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-blue-50 py-12 px-4">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-4xl font-bold text-gray-900">Extra Materials</h1>
              <p className="text-gray-600">Browse notes, videos, links, and past questions</p>
            </div>
            {canManage && (
              <button
                onClick={() => router.push("/materials/upload")}
                className="flex items-center gap-2 px-6 py-3 bg-purple-600 text-white rounded-lg font-semibold hover:bg-purple-700 transition-colors"
              >
                <Upload className="w-5 h-5" />
                Upload Material
              </button>
            )}
          </div>

          {/* Materials Grid */}
          {materials.length === 0 ? (
            <div className="bg-white rounded-2xl shadow-lg p-12 text-center">
              <FileText className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h2 className="text-2xl font-bold text-gray-900 mb-2">No Materials Yet</h2>
              <p className="text-gray-600 mb-6">
                {canManage
                  ? "Upload your first study material to get started"
                  : "Check back later for study materials"}
              </p>
              {canManage && (
                <button
                  onClick={() => router.push("/materials/upload")}
                  className="px-6 py-3 bg-purple-600 text-white rounded-lg font-semibold hover:bg-purple-700 transition-colors"
                >
                  Upload First Material
                </button>
              )}
            </div>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {materials.map((material) => (
                <div key={material.id} className="bg-white rounded-xl shadow-lg overflow-hidden hover:shadow-xl transition-shadow">
                  {/* Thumbnail */}
                  <div className="h-48 bg-gradient-to-br from-purple-100 to-blue-100 flex items-center justify-center">
                    {material.material_type === "video" && <span className="text-6xl">🎥</span>}
                    {material.material_type === "link" && <span className="text-6xl">🔗</span>}
                    {material.material_type === "past_question" && <span className="text-6xl">📋</span>}
                    {material.material_type === "note" && <span className="text-6xl">📝</span>}
                    {!material.material_type && <FileText className="w-16 h-16 text-purple-600" />}
                  </div>

                  {/* Content */}
                  <div className="p-6">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="px-2 py-1 bg-purple-100 text-purple-700 text-xs font-semibold rounded">
                        {material.material_type?.replace("_", " ").toUpperCase() || "MATERIAL"}
                      </span>
                    </div>
                    <h3 className="text-lg font-bold text-gray-900 mb-2 line-clamp-2">
                      {material.title}
                    </h3>
                    {material.description && (
                      <p className="text-sm text-gray-600 mb-3 line-clamp-2">{material.description}</p>
                    )}
                    <p className="text-xs text-gray-500 mb-1">
                      {material.subject_name} {material.block_name && `• ${material.block_name}`}
                    </p>
                    <p className="text-xs text-gray-500 mb-4">
                      Uploaded by {material.uploaded_by_name}
                    </p>

                    {/* Actions */}
                    <div className="flex gap-2">
                      <button
                        onClick={() => window.open(material.file_url, "_blank")}
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors text-sm font-semibold"
                      >
                        <Eye className="w-4 h-4" />
                        View
                      </button>
                      {canManage && profile?.id === material.uploaded_by && (
                        <button
                          onClick={() => handleDelete(material.id)}
                          className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </AuthGuard>
  );
}
