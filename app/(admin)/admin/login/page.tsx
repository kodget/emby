"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ShieldAlert } from "lucide-react";
import { toast } from "sonner";

export default function AdminLogin() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Use the standard backend login endpoint
      const response = await authApi.login({ email, password });
      
      // Store token
      sessionStorage.setItem("token", response.tokens.access);
      sessionStorage.setItem("refreshToken", response.tokens.refresh);
      sessionStorage.setItem("user", JSON.stringify(response.user));

      // Check if user is admin
      if (response.user.is_superuser || response.user.is_staff) {
        toast.success("Welcome to the Admin Dashboard");
        router.push("/admin");
      } else {
        // Revoke if not an admin
        sessionStorage.removeItem("token");
        sessionStorage.removeItem("refreshToken");
        sessionStorage.removeItem("user");
        toast.error("Unauthorized: Admin access required.");
      }
    } catch (error: any) {
      toast.error(error.response?.data?.error || "Invalid credentials");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-md bg-white rounded-xl shadow-lg border border-gray-100 p-8">
        <div className="flex flex-col items-center mb-8">
          <div className="h-12 w-12 bg-primary/10 text-primary rounded-full flex items-center justify-center mb-4">
            <ShieldAlert className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Admin Portal</h1>
          <p className="text-sm text-gray-500 mt-1">Sign in with superuser credentials</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="email">Email or Username</Label>
            <Input
              id="email"
              type="text"
              placeholder="admin@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          
          <Button 
            type="submit" 
            className="w-full"
            disabled={loading}
          >
            {loading ? "Verifying..." : "Sign In to Dashboard"}
          </Button>
        </form>
      </div>
    </div>
  );
}
