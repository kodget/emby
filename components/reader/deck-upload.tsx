"use client";

import { useRef, useState } from "react";
import { FileUp, Loader2, Upload, X } from "lucide-react";
import { deckApi } from "@/lib/api";
import { uploadIntent, uploadOwner, type UploadIntent } from "@/lib/upload-intent";

interface DeckUploadProps {
  onSuccess?: (deckId: string) => void;
  onError?: (error: string) => void;
}

export function DeckUpload({ onSuccess, onError }: DeckUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const intentRef = useRef<UploadIntent | null>(null);

  const SUPPORTED_FORMATS = [".pdf", ".pptx", ".ppt", ".docx"];

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;
    setFile(null);
    intentRef.current = null;

    const fileExtension =
      "." + selectedFile.name.split(".").pop()?.toLowerCase();

    if (!SUPPORTED_FORMATS.includes(fileExtension)) {
      onError?.(
        `Unsupported file format. Supported: ${SUPPORTED_FORMATS.join(", ")}`,
      );
      return;
    }

    if (selectedFile.size === 0 || selectedFile.size > 100 * 1024 * 1024) {
      onError?.(selectedFile.size === 0 ? "The file is empty." : "Maximum file size is 100 MB.");
      return;
    }

    setFile(selectedFile);
    // Use filename as default title
    setTitle(selectedFile.name.replace(/\.[^/.]+$/, ""));
  };

  const handleUpload = async () => {
    if (uploading) return;
    if (!file || !title.trim()) {
      onError?.("Please select a file and enter a title");
      return;
    }

    try {
      setUploading(true);
      setProgress(0);

      intentRef.current = uploadIntent(intentRef.current, file, JSON.stringify([uploadOwner(), title.trim()]));
      const deck = await deckApi.uploadDeck(file, title.trim(), intentRef.current.requestId);
      setProgress(100);

      // Reset form
      intentRef.current = null;
      setFile(null);
      setTitle("");
      if (inputRef.current) {
        inputRef.current.value = "";
      }

      onSuccess?.(deck.id);
    } catch (error: any) {
      const details = error.response?.data;
      const message = typeof details?.detail === "string" ? details.detail
        : typeof details?.error === "string" ? details.error
        : "Upload failed. Please try again.";
      onError?.(message);
    } finally {
      setUploading(false);
      setProgress(0);
    }
  };

  const fileSize = file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : "";

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <div className="space-y-4">
        {/* File Input */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">
            Select Document
          </label>
          <div className="relative">
            <input
              ref={inputRef}
              type="file"
              accept={SUPPORTED_FORMATS.join(",")}
              onChange={handleFileSelect}
              disabled={uploading}
              className="hidden"
            />
            <button
              onClick={() => inputRef.current?.click()}
              disabled={uploading}
              className="flex w-full items-center justify-center gap-2 rounded-lg border-2 border-dashed border-gray-300 bg-gray-50 px-4 py-6 text-center hover:border-blue-400 hover:bg-blue-50 disabled:opacity-50 transition-colors"
            >
              <FileUp className="h-5 w-5 text-gray-400" />
              <div className="text-left">
                <p className="text-sm font-medium text-gray-700">
                  {file ? file.name : "Click to select a file"}
                </p>
                <p className="text-xs text-gray-500">
                  {file ? `${fileSize}` : `PDF, PPTX, PPT, DOCX • Max 100 MB`}
                </p>
              </div>
            </button>
          </div>

          {file && (
            <button
              disabled={uploading}
              onClick={() => {
                intentRef.current = null;
                setFile(null);
                if (inputRef.current) {
                  inputRef.current.value = "";
                }
              }}
              className="text-sm text-red-600 hover:text-red-700"
            >
              Clear selection
            </button>
          )}
        </div>

        {/* Title Input */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">
            Document Title
          </label>
          <input
            type="text"
            value={title}
            maxLength={200}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g., Anatomy Lecture 01"
            disabled={uploading}
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50"
          />
        </div>

        {/* Progress Bar */}
        {uploading && progress > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600">Uploading...</span>
              <span className="text-gray-500">{progress}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
              <div
                className="h-full bg-blue-500 transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Upload Button */}
        <button
          onClick={handleUpload}
          disabled={!file || !title.trim() || uploading}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
        >
          {uploading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <Upload className="h-4 w-4" />
              Upload Document
            </>
          )}
        </button>
      </div>

      {/* Supported Formats Info */}
      <div className="mt-4 rounded-lg bg-blue-50 p-3 text-sm text-blue-700">
        <p className="font-medium">Supported formats:</p>
        <ul className="mt-1 list-inside list-disc space-y-1">
          <li>PDF (.pdf)</li>
          <li>PowerPoint PPTX (.pptx)</li>
          <li>PowerPoint PPT (.ppt)</li>
          <li>Word Document (.docx)</li>
        </ul>
      </div>
    </div>
  );
}
