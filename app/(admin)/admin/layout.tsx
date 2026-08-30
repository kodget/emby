"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { authApi, adminApi } from "@/lib/api";
import { UserProfile } from "@/lib/api";
import { 
  LayoutDashboard, 
  Users, 
  BookOpen, 
  CreditCard,
  LogOut,
  Menu,
  X
} from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [schema, setSchema] = useState<any[]>([]);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // If we're on the login page, don't check auth here
    if (pathname === "/admin/login") {
      setLoading(false);
      return;
    }

    const checkAuth = async () => {
      try {
        const profile = await authApi.getProfile();
        if (!profile.is_superuser && !profile.is_staff) {
          router.push("/admin/login");
        } else {
          setUser(profile);
          // Fetch dynamic schema for admin sidebar
          try {
             const adminSchema = await adminApi.getSchema();
             setSchema(adminSchema);
          } catch (e) {
             console.error("Failed to load schema", e);
          }
        }
      } catch (error) {
        router.push("/admin/login");
      } finally {
        setLoading(false);
      }
    };
    
    checkAuth();
  }, [pathname, router]);

  if (pathname === "/admin/login") {
    return <>{children}</>;
  }

  if (loading) {
    return <div className="flex h-screen w-full items-center justify-center bg-gray-50"><div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div></div>;
  }

  if (!user) return null;

  const coreNavigation = [
    { name: "Dashboard", href: "/admin", icon: LayoutDashboard },
    { name: "Users", href: "/admin/users", icon: Users },
    { name: "Curriculum", href: "/admin/curriculum", icon: BookOpen },
    { name: "Payments", href: "/admin/payments", icon: CreditCard },
  ];

  const handleLogout = () => {
    sessionStorage.removeItem("token");
    sessionStorage.removeItem("refreshToken");
    sessionStorage.removeItem("user");
    router.push("/admin/login");
  };

  return (
    <div className="flex h-screen overflow-hidden bg-gray-100">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 z-20 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div 
        className={`fixed inset-y-0 left-0 z-30 w-64 transform bg-white border-r border-gray-200 transition-transform duration-300 lg:static lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        } flex flex-col overflow-y-auto`}
      >
        <div className="flex items-center justify-between h-16 px-6 border-b border-gray-200 shrink-0">
          <span className="text-xl font-bold text-primary">EMBY Admin</span>
          <button className="lg:hidden" onClick={() => setSidebarOpen(false)}>
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>
        <div className="flex flex-col py-4 shrink-0">
          <div className="px-6 mb-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">Core</div>
          {coreNavigation.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center px-6 py-2 text-sm font-medium ${
                  isActive 
                    ? "bg-primary/10 text-primary border-r-4 border-primary" 
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`}
                onClick={() => setSidebarOpen(false)}
              >
                <item.icon className={`w-5 h-5 mr-3 ${isActive ? "text-primary" : "text-gray-400"}`} />
                {item.name}
              </Link>
            )
          })}
        </div>

        {/* Dynamic Schema Navigation */}
        {schema.map((app) => (
          <div key={app.app_label} className="flex flex-col py-2 shrink-0">
            <div className="px-6 mb-1 mt-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">{app.app_name}</div>
            {app.models.map((model: any) => {
              const href = `/admin/manage/${app.app_label}/${model.model_name}`;
              const isActive = pathname.startsWith(href);
              return (
                <Link
                  key={model.model_name}
                  href={href}
                  className={`flex items-center px-6 py-1.5 text-sm font-medium ${
                    isActive 
                      ? "bg-primary/5 text-primary border-r-4 border-primary" 
                      : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                  }`}
                  onClick={() => setSidebarOpen(false)}
                >
                  <span className="ml-8">{model.verbose_name_plural}</span>
                </Link>
              );
            })}
          </div>
        ))}
        <div className="h-20 shrink-0"></div>
      </div>

      {/* Main Content */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Header */}
        <header className="flex items-center justify-between h-16 px-6 bg-white border-b border-gray-200">
          <button 
            className="text-gray-500 lg:hidden focus:outline-none"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="w-6 h-6" />
          </button>
          
          <div className="flex items-center space-x-4 ml-auto">
            <div className="flex items-center space-x-2">
              <span className="text-sm font-medium text-gray-700 hidden sm:block">
                {user.full_name || user.username}
              </span>
              <Avatar className="h-8 w-8">
                <AvatarImage src={user.photo_url || undefined} />
                <AvatarFallback className="bg-primary/20 text-primary">
                  {user.username.charAt(0).toUpperCase()}
                </AvatarFallback>
              </Avatar>
            </div>
            <button 
              onClick={handleLogout}
              className="flex items-center text-sm font-medium text-red-600 hover:text-red-700 transition-colors"
            >
              <LogOut className="w-4 h-4 mr-1" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </header>

        {/* Main scrollable area */}
        <main className="flex-1 overflow-y-auto bg-gray-50 p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
