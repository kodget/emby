"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { deckApi, type SlideDeck } from "@/lib/api";
import { DeckUpload } from "@/components/reader/deck-upload";
import { Loader2, FileText, Trash2, Eye } from "lucide-react";

export default function DecksPage() {
  const router = useRouter();
  const [decks, setDecks] = useState<SlideDeck[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);

  const loadDecks = async () => {
    try {
      setLoading(true);
      const data = await deckApi.listDecks();
      setDecks(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load decks");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDecks();
  }, []);

  const handleDelete = async (deckId: string) => {
    if (!confirm("Delete this deck? This cannot be undone.")) return;

    try {
      await deckApi.deleteDeck(deckId);
      setDecks(decks.filter((d) => d.id !== deckId));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to delete deck"
      );
    }
  };

  const handleUploadSuccess = (deckId: string) => {
    setUploadSuccess(true);
    loadDecks();
    setTimeout(() => {
      router.push(`/decks/${deckId}`);
    }, 1000);
  };

  const getStatusBadge = (status: string) => {
    const statusConfig: Record<string, { bg: string; text: string; label: string }> = {
      pending: { bg: "bg-yellow-100", text: "text-yellow-800", label: "Pending" },
      processing: { bg: "bg-blue-100", text: "text-blue-800", label: "Processing" },
      completed: { bg: "bg-green-100", text: "text-green-800", label: "Ready" },
      failed: { bg: "bg-red-100", text: "text-red-800", label: "Failed" },
    };

    const config = statusConfig[status] || statusConfig.pending;
    return (
      <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
        {config.label}
      </span>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="border-b bg-white px-4 py-6 sm:px-6 lg:px-8">
        <h1 className="text-3xl font-bold text-gray-900">Documents</h1>
        <p className="mt-1 text-sm text-gray-500">
          Upload and view PDF, PowerPoint, and Word documents
        </p>
      </div>

      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-3">
          {/* Upload Section */}
          <div className="lg:col-span-1">
            <div className="sticky top-8">
              <h2 className="mb-4 text-lg font-semibold text-gray-900">
                Upload New Document
              </h2>
              <DeckUpload
                onSuccess={handleUploadSuccess}
                onError={(err) => setError(err)}
              />
            </div>
          </div>

          {/* Decks List */}
          <div className="lg:col-span-2">
            <h2 className="mb-6 text-lg font-semibold text-gray-900">
              Your Documents
            </h2>

            {error && (
              <div className="mb-6 rounded-lg bg-red-50 p-4 text-sm text-red-700">
                {error}
              </div>
            )}

            {uploadSuccess && (
              <div className="mb-6 rounded-lg bg-green-50 p-4 text-sm text-green-700">
                Document uploaded successfully! Redirecting...
              </div>
            )}

            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
              </div>
            ) : decks.length === 0 ? (
              <div className="rounded-lg border-2 border-dashed border-gray-300 bg-gray-50 py-12 text-center">
                <FileText className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-2 text-sm font-medium text-gray-900">
                  No documents yet
                </h3>
                <p className="mt-1 text-sm text-gray-500">
                  Upload your first document to get started
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {decks.map((deck) => (
                  <div
                    key={deck.id}
                    className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm hover:shadow-md transition-shadow"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start space-x-4 flex-1">
                        <div className="mt-1">
                          <FileText className="h-8 w-8 text-blue-500" />
                        </div>
                        <div className="flex-1">
                          <h3 className="text-sm font-semibold text-gray-900">
                            {deck.title}
                          </h3>
                          <div className="mt-2 flex items-center space-x-4 text-sm text-gray-500">
                            <span>{deck.file_type.toUpperCase()}</span>
                            <span>
                              {(deck.file_size / 1024 / 1024).toFixed(2)} MB
                            </span>
                            <span>{deck.page_count} pages</span>
                            {getStatusBadge(deck.processing_status)}
                          </div>
                          {deck.processing_status === "failed" &&
                            deck.processing_error && (
                              <p className="mt-2 text-sm text-red-600">
                                Error: {deck.processing_error}
                              </p>
                            )}
                        </div>
                      </div>

                      <div className="flex items-center space-x-2">
                        {deck.processing_status === "completed" && (
                          <Link
                            href={`/decks/${deck.id}`}
                            className="inline-flex items-center space-x-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
                          >
                            <Eye className="h-4 w-4" />
                            <span>View</span>
                          </Link>
                        )}
                        <button
                          onClick={() => handleDelete(deck.id)}
                          className="inline-flex items-center space-x-2 rounded-lg bg-red-50 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-100 transition-colors"
                        >
                          <Trash2 className="h-4 w-4" />
                          <span>Delete</span>
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
