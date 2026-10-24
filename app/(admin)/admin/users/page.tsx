"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { isAxiosError } from "axios";
import { adminApi, UserProfile } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Search, CheckCircle2, XCircle, RefreshCw } from "lucide-react";
import { format } from "date-fns";

function actionErrorMessage(error: unknown, fallback: string) {
  if (isAxiosError(error)) {
    const data = error.response?.data;
    if (Array.isArray(data) && data.every((item) => typeof item === "string")) return data.join(" ");
    if (data && typeof data === "object") {
      const message = data.error || data.detail || data.rejection_reason;
      if (typeof message === "string") return message;
      if (Array.isArray(message)) return message.join(" ");
    }
  }
  return fallback;
}

export default function UsersAdminPage() {
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterRole, setFilterRole] = useState<string>("all");
  const [pendingHeads, setPendingHeads] = useState<UserProfile[]>([]);
  const [reviewingId, setReviewingId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [rejectingUser, setRejectingUser] = useState<UserProfile | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");
  const reviewInFlight = useRef(false);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, pending] = await Promise.all([
        adminApi.getUsers(),
        adminApi.getPendingClassHeadVerifications(),
      ]);
      setUsers(data);
      setPendingHeads(pending);
    } catch (err) {
      setError(actionErrorMessage(err, "Unable to load users. Please try again."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetchUsers(); }, [fetchUsers]);

  const reviewClassHead = async (user: UserProfile, approved: boolean) => {
    if (reviewInFlight.current) return;
    const reason = rejectionReason.trim();
    if (!approved && !reason) {
      setActionError("Please explain why this application is being rejected.");
      return;
    }
    reviewInFlight.current = true;
    setReviewingId(user.id);
    setActionError(null);
    setActionMessage(null);
    try {
      const result = await adminApi.verifyClassHead(user.user_id, approved, approved ? "" : reason);
      setPendingHeads((current) => current.filter((profile) => profile.id !== user.id));
      setUsers((current) => current.map((profile) => profile.id === user.id ? result.user : profile));
      setActionMessage(result.message);
      setRejectingUser(null);
      setRejectionReason("");
    } catch (err) {
      setActionError(actionErrorMessage(err, "Unable to save this decision. Please try again."));
    } finally {
      reviewInFlight.current = false;
      setReviewingId(null);
    }
  };

  const filteredUsers = users.filter(user => {
    const matchesSearch = 
      user.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
      user.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (user.full_name && user.full_name.toLowerCase().includes(searchTerm.toLowerCase()));
      
    const matchesRole = filterRole === "all" || user.class_role === filterRole;
    
    return matchesSearch && matchesRole;
  });

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative" role="alert">
        <strong className="font-bold">Error! </strong>
        <span className="block sm:inline">{error}</span>
        <Button variant="outline" className="ml-3" onClick={() => void fetchUsers()}>Try again</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">User Management</h1>
          <p className="text-gray-500 mt-1">View and manage all registered users.</p>
        </div>
        <Button variant="outline" disabled={reviewingId !== null} onClick={() => void fetchUsers()}>
          <RefreshCw className="mr-2 h-4 w-4" /> Refresh
        </Button>
      </div>

      {actionMessage && <p className="text-sm text-emerald-700" role="status">{actionMessage}</p>}
      {actionError && !rejectingUser && <p className="text-sm text-destructive" role="alert">{actionError}</p>}

      <Card className="border-none shadow-sm">
        <CardHeader className="pb-4">
          <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
            <div className="relative w-full sm:max-w-xs">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
              <Input 
                placeholder="Search users..." 
                className="pl-9"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <div className="flex gap-2 w-full sm:w-auto">
              <select 
                className="flex h-10 w-full sm:w-[150px] items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                value={filterRole}
                onChange={(e) => setFilterRole(e.target.value)}
              >
                <option value="all">All Roles</option>
                <option value="student">Student</option>
                <option value="class_head">Class Head</option>
                <option value="material_uploader">Content Uploader</option>
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-gray-500 uppercase bg-gray-50 border-y border-gray-200">
                <tr>
                  <th className="px-4 py-3 font-medium">User</th>
                  <th className="px-4 py-3 font-medium">Role</th>
                  <th className="px-4 py-3 font-medium">School / Class</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Joined</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredUsers.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                      No users found matching your filters.
                    </td>
                  </tr>
                ) : (
                  filteredUsers.map((user) => (
                    <tr key={user.id} className="hover:bg-gray-50">
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-3">
                          <Avatar className="h-9 w-9">
                            <AvatarImage src={user.photo_url || undefined} />
                            <AvatarFallback className="bg-primary/10 text-primary">
                              {user.username.charAt(0).toUpperCase()}
                            </AvatarFallback>
                          </Avatar>
                          <div>
                            <div className="font-medium text-gray-900">{user.full_name || user.username}</div>
                            <div className="text-gray-500 text-xs">{user.email}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <Badge variant="outline" className="capitalize text-xs">
                          {user.class_role?.replace('_', ' ') || 'None'}
                        </Badge>
                      </td>
                      <td className="px-4 py-4">
                        <div className="text-gray-900">{user.school_name || '-'}</div>
                        <div className="text-gray-500 text-xs">{user.class_code ? `Class: ${user.class_code}` : ''}</div>
                      </td>
                      <td className="px-4 py-4">
                        {user.class_role === "class_head" && (
                          <Badge variant={user.class_head_verified ? "outline" : "secondary"} className="mr-2">
                            {user.class_head_verified ? "Verified" : user.class_head_verification_requested ? "Pending review" : "Not approved"}
                          </Badge>
                        )}
                        {user.is_premium ? (
                          <Badge className="bg-emerald-100 text-emerald-800 hover:bg-emerald-100 border-emerald-200">Premium</Badge>
                        ) : (
                          <Badge variant="secondary" className="bg-gray-100">Free</Badge>
                        )}
                        {!user.can_access_app && (
                          <Badge variant="destructive" className="ml-2">Restricted</Badge>
                        )}
                      </td>
                      <td className="px-4 py-4 text-gray-500 text-xs whitespace-nowrap">
                        {user.created_at ? format(new Date(user.created_at), 'MMM d, yyyy') : 'Unknown'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

        <Card className="border-amber-200 shadow-sm">
          <CardHeader>
            <CardTitle>Pending class-head approvals</CardTitle>
            <CardDescription>Review each application. Each class can have up to three approved class heads.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {pendingHeads.length === 0 && <p className="text-sm text-muted-foreground">No class-head applications are waiting for review.</p>}
            {pendingHeads.map((user) => (
              <div key={user.id} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-lg border p-3">
                <div>
                  <p className="font-medium">{user.full_name || user.username}</p>
                  <p className="text-sm text-muted-foreground">{user.email}</p>
                  <p className="text-xs text-muted-foreground">{user.school_name || "No school"} · {user.set_name || "No class"}</p>
                </div>
                <div className="flex gap-2">
                  <Button onClick={() => void reviewClassHead(user, true)} disabled={reviewingId !== null} aria-label={`Approve ${user.full_name || user.username}`}>
                    <CheckCircle2 className="mr-2 h-4 w-4" />
                    {reviewingId === user.id ? "Saving…" : "Approve"}
                  </Button>
                  <Button variant="outline" disabled={reviewingId !== null} onClick={() => {
                    setRejectingUser(user);
                    setRejectionReason("");
                    setActionError(null);
                  }} aria-label={`Reject ${user.full_name || user.username}`}>
                    <XCircle className="mr-2 h-4 w-4" />Reject
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      <Dialog open={rejectingUser !== null} onOpenChange={(open) => {
        if (!open && reviewingId === null) {
          setRejectingUser(null);
          setActionError(null);
        }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject class-head application</DialogTitle>
            <DialogDescription>
              Explain your decision to {rejectingUser?.full_name || rejectingUser?.username}. This reason will appear on their verification page.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="rejection-reason">Reason for rejection</Label>
            <Textarea id="rejection-reason" value={rejectionReason} onChange={(event) => setRejectionReason(event.target.value)} required disabled={reviewingId !== null} rows={4} />
          </div>
          {actionError && <p className="text-sm text-destructive" role="alert">{actionError}</p>}
          <DialogFooter>
            <Button variant="outline" disabled={reviewingId !== null} onClick={() => {
              setRejectingUser(null);
              setActionError(null);
            }}>Cancel</Button>
            <Button variant="destructive" disabled={reviewingId !== null || !rejectionReason.trim()} onClick={() => rejectingUser && void reviewClassHead(rejectingUser, false)}>
              {reviewingId !== null ? "Saving…" : "Reject application"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
