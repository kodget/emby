"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { curriculumApi, authApi } from "@/lib/api";
import { Subject, Block, Topic, Section, UserProfile } from "@/lib/api";
import AuthGuard from "@/components/auth/auth-guard";
import { canUploadMaterials } from "@/lib/guards";
import { Upload, FileText, CheckCircle, XCircle, Loader, ArrowLeft } from "lucide-react";

export default function MaterialUploadPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [sections, setSections] = useState<Section[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [uploadType, setUploadType] = useState<"slide" | "material">("slide");
  const [formData, setFormData] = useState({
    title: "",
    description: "",
    materialType: "" as "pdf" | "pptx" | "docx" | "video" | "image" | "past_question" | "other" | "",
    linkUrl: "",
    subject: "",
    block: "",
    section: "",
    file: null as File | null,
  });

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (formData.subject) {
      loadBlocks(formData.subject);
    }
  }, [formData.subject]);

  useEffect(() => {
    if (formData.block) {
      loadSections(formData.block);
    }
  }, [formData.block]);

  const loadData = async () => {
    try {
      console.log('Loading profile...');
      const profileData = await authApi.getProfile();
      console.log('Profile loaded:', profileData);
      setProfile(profileData);

      if (!canUploadMaterials()) {
        console.log('User cannot upload materials, redirecting...');
        router.push("/dashboard");
        return;
      }

      console.log('Fetching subjects from API...');
      const subjectsData = await curriculumApi.getSubjects();
      console.log('Subjects loaded:', subjectsData);
      setSubjects(subjectsData);
    } catch (error) {
      console.error("Failed to load data:", error);
      alert(`Failed to load data: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const loadBlocks = async (subjectId: string) => {
    try {
      const blocksData = await curriculumApi.getBlocks(subjectId);
      setBlocks(blocksData);
      setSections([]);
      setFormData(prev => ({ ...prev, block: "", section: "" }));
    } catch (error) {
      console.error("Failed to load blocks:", error);
    }
  };

  const loadSections = async (blockId: string) => {
    try {
      const sectionsData = await curriculumApi.getSections({ block: blockId });
      setSections(sectionsData);
      setFormData(prev => ({ ...prev, section: "" }));
    } catch (error) {
      console.error("Failed to load sections:", error);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 100 * 1024 * 1024) {
        alert("File size must be less than 100MB");
        return;
      }
      setFormData(prev => ({ ...prev, file }));
      
      // Auto-detect file type
      const ext = file.name.split('.').pop()?.toLowerCase();
      if (ext === 'pdf') setFormData(prev => ({ ...prev, materialType: 'pdf' }));
      else if (ext === 'pptx' || ext === 'ppt') setFormData(prev => ({ ...prev, materialType: 'pptx' }));
      else if (ext === 'docx' || ext === 'doc') setFormData(prev => ({ ...prev, materialType: 'docx' }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.file && !formData.linkUrl) {
      alert("Please select a file or enter a link");
      return;
    }

    if (!formData.subject || !formData.block) {
      alert("Please select course and block");
      return;
    }

    setUploading(true);
    setUploadStatus("uploading");

    try {
      let fileUrl = formData.linkUrl;

      // Upload file if provided
      if (formData.file) {
        const uploadFormData = new FormData();
        uploadFormData.append("file", formData.file);
        uploadFormData.append("type", uploadType === "slide" ? "slides" : "materials");

        console.log('Uploading file to Cloudinary...');
        const uploadResponse = await fetch("http://localhost:8000/api/upload/", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${localStorage.getItem("token")}`,
          },
          body: uploadFormData,
        });

        if (!uploadResponse.ok) {
          const errorData = await uploadResponse.json().catch(() => ({ error: 'Upload failed' }));
          console.error('Upload error:', errorData);
          throw new Error(errorData.error || "Failed to upload file to Cloudinary");
        }

        const uploadData = await uploadResponse.json();
        console.log('File uploaded successfully:', uploadData);
        fileUrl = uploadData.url;
        
        if (!fileUrl) {
          throw new Error("No file URL returned from upload");
        }
      }

      if (!fileUrl) {
        throw new Error("No file URL available");
      }

      console.log('Creating record with file URL:', fileUrl);

      if (uploadType === "slide") {
        // Create slide (for PDF/PPT/DOCX only)
        const slideData = {
          title: formData.title,
          subject: formData.subject,
          block: formData.block,
          section: formData.section || undefined,
          file_url: fileUrl,
          file_type: formData.materialType,
          page_count: 0, // Will be updated after processing
        };
        
        console.log('Creating slide with data:', slideData);
        const createdSlide = await curriculumApi.createSlide(slideData);
        console.log('Slide created successfully:', createdSlide);
      } else {
        // Create material (for other types)
        const materialData = {
          title: formData.title,
          description: formData.description,
          material_type: formData.materialType,
          subject: formData.subject,
          block: formData.block,
          section: formData.section || undefined,
          file_url: fileUrl,
          file_size: formData.file?.size || 0,
        };
        
        console.log('Creating material with data:', materialData);
        const createdMaterial = await curriculumApi.createMaterial(materialData);
        console.log('Material created successfully:', createdMaterial);
      }

      setUploadStatus("success");
      setTimeout(() => {
        router.push("/courses");
      }, 1500);
    } catch (error) {
      console.error("Failed to upload:", error);
      alert(error instanceof Error ? error.message : "Upload failed. Please try again.");
      setUploadStatus("error");
      setTimeout(() => setUploadStatus("idle"), 3000);
    } finally {
      setUploading(false);
    }
  };

  if (loading) {
    return (
      <AuthGuard>
        <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-blue-50 flex items-center justify-center">
          <div className="text-center">
            <div className="w-16 h-16 border-4 border-purple-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-gray-600">Loading...</p>
          </div>
        </div>
      </AuthGuard>
    );
  }

  return (
    <AuthGuard>
      <div className="min-h-screen bg-gradient-to-br from-purple-50 via-white to-blue-50 py-12 px-4">
        <div className="max-w-4xl mx-auto">
          {/* Header */}
          <div className="flex items-center gap-4 mb-8">
            <button
              onClick={() => router.back()}
              className="p-2 hover:bg-white rounded-lg transition-colors"
            >
              <ArrowLeft className="w-6 h-6 text-gray-600" />
            </button>
            <div>
              <h1 className="text-4xl font-bold text-gray-900">Upload Content</h1>
              <p className="text-gray-600">Share slides and materials with your class</p>
            </div>
          </div>

          {/* Upload Form */}
          <div className="bg-white rounded-2xl shadow-lg p-8">
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Upload Type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  What are you uploading? <span className="text-red-500">*</span>
                </label>
                <div className="grid grid-cols-2 gap-4">
                  <button
                    type="button"
                    onClick={() => setUploadType("slide")}
                    className={`p-4 border-2 rounded-lg text-center transition-all ${
                      uploadType === "slide"
                        ? "border-purple-600 bg-purple-50"
                        : "border-gray-300 hover:border-purple-300"
                    }`}
                  >
                    <div className="text-3xl mb-2">📄</div>
                    <div className="font-semibold text-gray-900">Slide</div>
                    <div className="text-xs text-gray-600">PDF/PPT/DOCX for reading</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => setUploadType("material")}
                    className={`p-4 border-2 rounded-lg text-center transition-all ${
                      uploadType === "material"
                        ? "border-purple-600 bg-purple-50"
                        : "border-gray-300 hover:border-purple-300"
                    }`}
                  >
                    <div className="text-3xl mb-2">📚</div>
                    <div className="font-semibold text-gray-900">Material</div>
                    <div className="text-xs text-gray-600">Videos, images, past questions</div>
                  </button>
                </div>
              </div>

              {/* Title */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Title <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  required
                  placeholder="e.g., Upper Limb Anatomy Lecture"
                />
              </div>

              {/* Description (for materials only) */}
              {uploadType === "material" && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Description <span className="text-gray-500">(Optional)</span>
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    rows={3}
                    placeholder="Brief description"
                  />
                </div>
              )}

              {/* Course (Subject) */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Course <span className="text-red-500">*</span>
                </label>
                <select
                  value={formData.subject}
                  onChange={(e) => setFormData(prev => ({ ...prev, subject: e.target.value }))}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  required
                >
                  <option value="">Select Course</option>
                  {subjects.map((subject) => (
                    <option key={subject.id} value={subject.id}>
                      {subject.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Block */}
              {formData.subject && blocks.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Block <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={formData.block}
                    onChange={(e) => setFormData(prev => ({ ...prev, block: e.target.value }))}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    required
                  >
                    <option value="">Select Block</option>
                    {blocks.map((block) => (
                      <option key={block.id} value={block.id}>
                        {block.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Section */}
              {formData.block && sections.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Section <span className="text-gray-500">(Optional)</span>
                  </label>
                  <select
                    value={formData.section}
                    onChange={(e) => setFormData(prev => ({ ...prev, section: e.target.value }))}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  >
                    <option value="">Select Section (or skip)</option>
                    {sections.map((section) => (
                      <option key={section.id} value={section.id}>
                        {section.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* File Upload */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  File <span className="text-red-500">*</span>
                </label>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-purple-500 transition-colors">
                  <input
                    type="file"
                    accept={uploadType === "slide" ? ".pdf,.ppt,.pptx,.doc,.docx" : "*"}
                    onChange={handleFileChange}
                    className="hidden"
                    id="file-upload"
                  />
                  <label htmlFor="file-upload" className="cursor-pointer">
                    <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                    {formData.file ? (
                      <div>
                        <p className="text-lg font-semibold text-gray-900 mb-1">{formData.file.name}</p>
                        <p className="text-sm text-gray-600">
                          {(formData.file.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.preventDefault();
                            setFormData(prev => ({ ...prev, file: null }));
                          }}
                          className="mt-2 text-sm text-red-600 hover:text-red-700"
                        >
                          Remove file
                        </button>
                      </div>
                    ) : (
                      <div>
                        <p className="text-lg font-semibold text-gray-900 mb-1">
                          Click to upload
                        </p>
                        <p className="text-sm text-gray-600">
                          {uploadType === "slide" ? "PDF, PPT, DOCX (max 100MB)" : "Any file type (max 100MB)"}
                        </p>
                      </div>
                    )}
                  </label>
                </div>
              </div>

              {/* Submit Button */}
              <div className="flex gap-4 pt-4">
                <button
                  type="submit"
                  disabled={uploading}
                  className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-purple-600 text-white rounded-lg font-semibold hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {uploadStatus === "uploading" && <Loader className="w-5 h-5 animate-spin" />}
                  {uploadStatus === "success" && <CheckCircle className="w-5 h-5" />}
                  {uploadStatus === "error" && <XCircle className="w-5 h-5" />}
                  {uploadStatus === "idle" && <Upload className="w-5 h-5" />}
                  {uploadStatus === "uploading" && "Uploading..."}
                  {uploadStatus === "success" && "Uploaded Successfully!"}
                  {uploadStatus === "error" && "Upload Failed"}
                  {uploadStatus === "idle" && `Upload ${uploadType === "slide" ? "Slide" : "Material"}`}
                </button>
                <button
                  type="button"
                  onClick={() => router.back()}
                  className="px-6 py-3 bg-gray-300 text-gray-700 rounded-lg font-semibold hover:bg-gray-400 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </AuthGuard>
  );
}
