"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { communityApi, authApi } from "@/lib/api";
import { CommunityPost, UserProfile } from "@/lib/api";
import AuthGuard from "@/components/auth/auth-guard";
import { isPremium } from "@/lib/guards";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  InputGroup,
  InputGroupInput,
  InputGroupAddon,
} from "@/components/ui/input-group";
import {
  ArrowUp,
  MessageCircle,
  Search,
  Plus,
  Megaphone,
  BookOpen,
  Stethoscope,
  CheckCheck,
  Send,
  Lock,
  Crown,
  Edit2,
  Trash2,
  MoreVertical,
} from "lucide-react";
import { cn } from "@/lib/utils";

const roleMeta: Record<
  string,
  {
    label: string;
    className: string;
    icon: React.ComponentType<{ className?: string }>;
  }
> = {
  "class-rep": {
    label: "Class Rep",
    className: "bg-accent/15 text-accent",
    icon: Megaphone,
  },
  "top-student": {
    label: "Top Student",
    className: "bg-primary/10 text-primary",
    icon: CheckCheck,
  },
  student: {
    label: "Student",
    className: "bg-secondary text-secondary-foreground",
    icon: BookOpen,
  },
  teacher: {
    label: "Teacher",
    className: "bg-primary/10 text-primary",
    icon: BookOpen,
  },
};

const postTypeColors: Record<string, string> = {
  achievement: "bg-green-100 text-green-700",
  question: "bg-blue-100 text-blue-700",
  discussion: "bg-purple-100 text-purple-700",
  resource: "bg-orange-100 text-orange-700",
};

const postTypeLabels: Record<string, string> = {
  achievement: "Achievement",
  question: "Question",
  discussion: "Discussion",
  resource: "Resource",
};

export default function CommunityPage() {
  const router = useRouter();
  const [posts, setPosts] = useState<CommunityPost[]>([]);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newPost, setNewPost] = useState({
    post_type: "discussion" as
      | "achievement"
      | "question"
      | "discussion"
      | "resource",
    content: "",
  });
  const [commentInputs, setCommentInputs] = useState<{
    [key: number]: string;
  }>({});
  const [submitting, setSubmitting] = useState(false);
  const [filter, setFilter] = useState("All");
  const [editingPost, setEditingPost] = useState<number | null>(null);
  const [editContent, setEditContent] = useState("");

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [postsData, profileData] = await Promise.all([
        communityApi.getPosts(),
        authApi.getProfile(),
      ]);
      setPosts(postsData);
      setProfile(profileData);
    } catch (error) {
      console.error("Failed to load data:", error);
    } finally {
      setLoading(false);
    }
  };

  const hasPremium = isPremium();

  const handleCreatePost = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hasPremium) {
      router.push("/payment");
      return;
    }
    setSubmitting(true);
    try {
      await communityApi.createPost(newPost);
      await loadData();
      setShowCreateModal(false);
      setNewPost({ post_type: "discussion", content: "" });
    } catch (error) {
      console.error("Failed to create post:", error);
    } finally {
      setSubmitting(false);
    }
  };

  const handleLike = async (postId: number) => {
    if (!hasPremium) {
      router.push("/payment");
      return;
    }
    try {
      await communityApi.likePost(postId);
      await loadData();
    } catch (error) {
      console.error("Failed to like post:", error);
    }
  };

  const handleComment = async (postId: number) => {
    if (!hasPremium) {
      router.push("/payment");
      return;
    }
    const content = commentInputs[postId]?.trim();
    if (!content) return;

    try {
      await communityApi.addComment(postId, content);
      setCommentInputs({ ...commentInputs, [postId]: "" });
      await loadData();
    } catch (error) {
      console.error("Failed to add comment:", error);
    }
  };

  const handleEditPost = (post: CommunityPost) => {
    setEditingPost(post.id);
    setEditContent(post.content);
  };

  const handleUpdatePost = async (postId: number) => {
    if (!editContent.trim()) return;
    setSubmitting(true);
    try {
      await communityApi.updatePost(postId, { content: editContent });
      setEditingPost(null);
      setEditContent("");
      await loadData();
    } catch (error) {
      console.error("Failed to update post:", error);
      alert("Failed to update post");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeletePost = async (postId: number) => {
    if (!confirm("Are you sure you want to delete this post?")) return;
    try {
      await communityApi.deletePost(postId);
      await loadData();
    } catch (error) {
      console.error("Failed to delete post:", error);
      alert("Failed to delete post");
    }
  };

  const filteredPosts =
    filter === "All"
      ? posts
      : posts.filter(
          (p) =>
            p.post_type === filter.toLowerCase() ||
            p.content?.toLowerCase().includes(filter.toLowerCase()),
        );

  if (loading) {
    return (
      <AuthGuard>
        <div className="flex min-h-[60vh] items-center justify-center">
          <div className="text-center">
            <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
            <p className="text-muted-foreground">Loading community...</p>
          </div>
        </div>
      </AuthGuard>
    );
  }

  return (
    <AuthGuard>
      <div className="mx-auto max-w-5xl px-4 py-8 md:py-12">
        <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
              <Stethoscope className="h-3.5 w-3.5 text-primary" />
              BMS Students · Your school
            </div>
            <h1 className="mt-3 font-serif text-4xl font-semibold tracking-tight md:text-5xl">
              Community
            </h1>
            <p className="mt-2 max-w-xl text-muted-foreground">
              Ask questions, share past papers, and learn from top students and
              your class reps. No strangers — only people in your program.
            </p>
          </div>
          <div className="flex gap-2">
            <InputGroup className="w-full md:w-64">
              <InputGroupAddon>
                <Search className="h-4 w-4" />
              </InputGroupAddon>
              <InputGroupInput placeholder="Search threads…" />
            </InputGroup>
            {hasPremium ? (
              <Button onClick={() => setShowCreateModal(true)}>
                <Plus className="mr-1 h-4 w-4" />
                Ask
              </Button>
            ) : (
              <Button
                variant="secondary"
                onClick={() => router.push("/payment")}
              >
                <Lock className="mr-1 h-4 w-4" />
                Ask
              </Button>
            )}
          </div>
        </header>

        {/* Free User Banner */}
        {!hasPremium && (
          <div className="mb-8 rounded-2xl border border-primary/20 bg-primary/5 p-6">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary/10">
                <Crown className="h-6 w-6 text-primary" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold">
                  Community Engagement is a Premium Feature
                </h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  You can read posts, but to create posts, like, or comment, you
                  need to upgrade to Premium.
                </p>
                <Button
                  className="mt-3"
                  size="sm"
                  onClick={() => router.push("/payment")}
                >
                  Upgrade to Premium
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="mb-6 flex flex-wrap items-center gap-2">
          <p className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
            Filter
          </p>
          {["All", "Question", "Discussion", "Achievement", "Resource"].map(
            (f) => (
              <FilterChip
                key={f}
                label={f}
                active={filter === f}
                onClick={() => setFilter(f)}
              />
            ),
          )}
        </div>

        <section>
          <p className="mb-3 text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
            Recent threads
          </p>

          {filteredPosts.length === 0 ? (
            <Card className="p-12 text-center">
              <MessageCircle className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
              <h2 className="text-xl font-semibold">No Posts Yet</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Be the first to start a conversation!
              </p>
              {hasPremium && (
                <Button
                  className="mt-4"
                  onClick={() => setShowCreateModal(true)}
                >
                  <Plus className="mr-1 h-4 w-4" />
                  Create First Post
                </Button>
              )}
            </Card>
          ) : (
            <div className="space-y-3">
              {filteredPosts.map((p) => (
                <Card
                  key={p.id}
                  className="border-border/60 p-5 transition-colors hover:border-primary/40"
                >
                  <PostInner
                    post={p}
                    hasPremium={hasPremium}
                    currentUserId={profile?.id}
                    onLike={() => handleLike(p.id)}
                    commentInput={commentInputs[p.id] || ""}
                    onCommentChange={(v) =>
                      setCommentInputs({ ...commentInputs, [p.id]: v })
                    }
                    onCommentSubmit={() => handleComment(p.id)}
                    onEdit={() => handleEditPost(p)}
                    onDelete={() => handleDeletePost(p.id)}
                    isEditing={editingPost === p.id}
                    editContent={editContent}
                    onEditContentChange={setEditContent}
                    onSaveEdit={() => handleUpdatePost(p.id)}
                    onCancelEdit={() => {
                      setEditingPost(null);
                      setEditContent("");
                    }}
                    submitting={submitting}
                  />
                </Card>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Create Post Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-2xl rounded-2xl bg-card p-8 shadow-2xl">
            <h2 className="mb-6 text-2xl font-bold">Create Post</h2>
            <form onSubmit={handleCreatePost} className="space-y-4">
              <div>
                <label className="mb-2 block text-sm font-medium">
                  Post Type
                </label>
                <select
                  value={newPost.post_type}
                  onChange={(e) =>
                    setNewPost({
                      ...newPost,
                      post_type: e.target.value as typeof newPost.post_type,
                    })
                  }
                  className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm outline-none focus:border-primary"
                >
                  <option value="discussion">Discussion</option>
                  <option value="question">Question</option>
                  <option value="achievement">Achievement</option>
                  <option value="resource">Resource</option>
                </select>
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium">
                  Content
                </label>
                <textarea
                  value={newPost.content}
                  onChange={(e) =>
                    setNewPost({ ...newPost, content: e.target.value })
                  }
                  rows={6}
                  className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm outline-none focus:border-primary"
                  required
                  placeholder="Share your thoughts..."
                />
              </div>
              <div className="flex gap-3 pt-4">
                <Button type="submit" disabled={submitting} className="flex-1">
                  {submitting ? "Posting..." : "Post"}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  className="flex-1"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AuthGuard>
  );
}

function PostInner({
  post,
  hasPremium,
  currentUserId,
  onLike,
  commentInput,
  onCommentChange,
  onCommentSubmit,
  onEdit,
  onDelete,
  isEditing,
  editContent,
  onEditContentChange,
  onSaveEdit,
  onCancelEdit,
  submitting,
}: {
  post: CommunityPost;
  hasPremium: boolean;
  currentUserId?: number;
  onLike: () => void;
  commentInput: string;
  onCommentChange: (v: string) => void;
  onCommentSubmit: () => void;
  onEdit: () => void;
  onDelete: () => void;
  isEditing: boolean;
  editContent: string;
  onEditContentChange: (v: string) => void;
  onSaveEdit: () => void;
  onCancelEdit: () => void;
  submitting: boolean;
}) {
  const [showMenu, setShowMenu] = useState(false);
  const isOwner = currentUserId === post.user;

  return (
    <div className="flex gap-4">
      {/* Vote column */}
      <div className="flex shrink-0 flex-col items-center gap-1">
        <button
          onClick={onLike}
          disabled={!hasPremium}
          className={cn(
            "flex size-8 items-center justify-center rounded-full border border-border bg-background transition-colors",
            hasPremium
              ? "hover:border-primary hover:text-primary"
              : "cursor-not-allowed opacity-50",
          )}
        >
          <ArrowUp className="h-4 w-4" />
        </button>
        <span className="text-sm font-semibold tabular-nums">
          {post.likes_count}
        </span>
      </div>

      {/* Body */}
      <div className="flex-1">
        <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Link href={`/profile/${post.user}`} className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            <Avatar className="size-6">
              <AvatarImage
                src={post.user_photo || "/placeholder.svg"}
                alt={post.user_name}
              />
              <AvatarFallback>{post.user_name?.[0] || "?"}</AvatarFallback>
            </Avatar>
            <span className="font-medium text-foreground hover:underline">{post.user_name}</span>
          </Link>
          <Badge
            className={cn(
              "gap-1 border-0",
              postTypeColors[post.post_type] ||
                "bg-secondary text-secondary-foreground",
            )}
          >
            {postTypeLabels[post.post_type] || "Post"}
          </Badge>
          <span>·</span>
          <span>{new Date(post.created_at).toLocaleDateString()}</span>
          
          {/* Edit/Delete Menu */}
          {isOwner && (
            <div className="ml-auto relative">
              <button
                onClick={() => setShowMenu(!showMenu)}
                className="p-1 hover:bg-muted rounded-md transition-colors"
              >
                <MoreVertical className="h-4 w-4" />
              </button>
              {showMenu && (
                <div className="absolute right-0 mt-1 w-32 bg-card border border-border rounded-lg shadow-lg z-10">
                  <button
                    onClick={() => {
                      onEdit();
                      setShowMenu(false);
                    }}
                    className="w-full px-3 py-2 text-left text-sm hover:bg-muted flex items-center gap-2 rounded-t-lg"
                  >
                    <Edit2 className="h-3.5 w-3.5" />
                    Edit
                  </button>
                  <button
                    onClick={() => {
                      onDelete();
                      setShowMenu(false);
                    }}
                    className="w-full px-3 py-2 text-left text-sm hover:bg-muted flex items-center gap-2 text-red-600 rounded-b-lg"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Delete
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {isEditing ? (
          <div className="space-y-3">
            <textarea
              value={editContent}
              onChange={(e) => onEditContentChange(e.target.value)}
              rows={4}
              className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm outline-none focus:border-primary"
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={onSaveEdit} disabled={submitting}>
                {submitting ? "Saving..." : "Save"}
              </Button>
              <Button size="sm" variant="secondary" onClick={onCancelEdit}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <p className="mt-2 text-sm whitespace-pre-wrap text-foreground">
            {post.content}
          </p>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <MessageCircle className="h-3.5 w-3.5" />
            {post.comments_count || 0}{" "}
            {(post.comments_count || 0) === 1 ? "comment" : "comments"}
          </span>
        </div>

        {/* Comments */}
        {post.comments && post.comments.length > 0 && (
          <div className="mt-4 space-y-3 border-t pt-4">
            {post.comments.map((comment) => (
              <div key={comment.id} className="flex gap-3">
                <Avatar className="size-6">
                  <AvatarFallback>
                    {comment.user_name?.[0] || "?"}
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1 rounded-lg bg-muted p-3">
                  <div className="text-xs font-semibold">
                    {comment.user_name}
                  </div>
                  <p className="mt-1 text-sm">{comment.content}</p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Add Comment */}
        <div className="mt-4 flex gap-3">
          <InputGroup className="flex-1">
            <InputGroupInput
              value={commentInput}
              onChange={(e) => onCommentChange(e.target.value)}
              placeholder={
                hasPremium
                  ? "Add a comment..."
                  : "Upgrade to Premium to comment..."
              }
              disabled={!hasPremium}
              onKeyDown={(e) => e.key === "Enter" && onCommentSubmit()}
            />
          </InputGroup>
          <Button
            size="icon"
            disabled={!hasPremium || !commentInput.trim()}
            onClick={onCommentSubmit}
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1 text-xs transition-colors",
        active
          ? "border-foreground bg-foreground text-background"
          : "border-border bg-card text-muted-foreground hover:border-foreground/40 hover:text-foreground",
      )}
    >
      {label}
    </button>
  );
}
