"use client";

import { useEffect, useState } from "react";
import { adminApi, UserProfile } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Search, Filter, Ban, MoreVertical } from "lucide-react";
import { format } from "date-fns";

export default function UsersAdminPage() {
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterRole, setFilterRole] = useState<string>("all");

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const data = await adminApi.getUsers();
        setUsers(data);
      } catch (err: any) {
        setError(err.message || "Failed to load users");
      } finally {
        setLoading(false);
      }
    };
    fetchUsers();
  }, []);

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
      </div>

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
                  <th className="px-4 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredUsers.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
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
                      <td className="px-4 py-4 text-right">
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-gray-500">
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
