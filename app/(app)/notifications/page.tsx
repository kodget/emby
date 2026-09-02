"use client";

import { useEffect } from "react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { fetchNotifications, markRead } from "@/store/notifications-slice";
import { Bell, Check, ArrowRight } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { useRouter } from "next/navigation";
import AuthGuard from "@/components/auth/auth-guard";
import { Button } from "@/components/ui/button";

export default function NotificationsPage() {
  const dispatch = useAppDispatch();
  const router = useRouter();
  const { items, unreadCount, status } = useAppSelector(
    (state) => state.notifications
  );

  useEffect(() => {
    if (status === "idle") {
      dispatch(fetchNotifications());
    }
  }, [dispatch, status]);

  const handleMarkAllRead = () => {
    dispatch(markRead());
  };

  const handleNotificationClick = (notification: any) => {
    if (!notification.read) {
      dispatch(markRead(notification.id));
    }
    if (notification.action_url) {
      router.push(notification.action_url);
    }
  };

  return (
    <AuthGuard>
      <div className="min-h-screen px-4 py-6 sm:px-6">
        <div className="max-w-4xl mx-auto">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-8 gap-4">
            <h1 className="text-4xl font-bold text-gray-900 flex items-center gap-3">
              <Bell className="w-8 h-8 text-primary" />
              Notifications
            </h1>
            {unreadCount > 0 && (
              <Button
                variant="outline"
                className="shrink-0"
                onClick={handleMarkAllRead}
              >
                <Check className="mr-2 size-4" />
                Mark all as read
              </Button>
            )}
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-border overflow-hidden">
            {status === "loading" && items.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">
                Loading notifications...
              </div>
            ) : items.length === 0 ? (
              <div className="p-16 text-center flex flex-col items-center justify-center space-y-4">
                <div className="flex size-16 items-center justify-center rounded-full bg-muted/50 text-muted-foreground">
                  <Bell className="size-8 opacity-50" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-foreground">
                    You're all caught up!
                  </h3>
                  <p className="text-muted-foreground mt-1">
                    You have no notifications right now.
                  </p>
                </div>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {items.map((n) => (
                  <div
                    key={n.id}
                    onClick={() => handleNotificationClick(n)}
                    className={`flex cursor-pointer items-start gap-4 p-4 sm:p-6 transition-colors hover:bg-muted/50 ${
                      !n.read ? "bg-primary/5" : ""
                    }`}
                  >
                    <div className="mt-1 flex-shrink-0">
                      {n.read ? (
                        <div className="size-2 rounded-full bg-transparent" />
                      ) : (
                        <div className="size-2 rounded-full bg-primary shadow-sm" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 sm:gap-4 mb-1">
                        <h4
                          className={`font-semibold text-base ${
                            !n.read ? "text-foreground" : "text-muted-foreground"
                          }`}
                        >
                          {n.title}
                        </h4>
                        <span className="text-xs text-muted-foreground whitespace-nowrap">
                          {formatDistanceToNow(new Date(n.created_at), {
                            addSuffix: true,
                          })}
                        </span>
                      </div>
                      {n.body && (
                        <p className="text-sm text-muted-foreground/90 leading-relaxed max-w-3xl">
                          {n.body}
                        </p>
                      )}
                      {n.action_url && (
                        <div className="mt-3 flex items-center text-sm font-medium text-primary">
                          View details
                          <ArrowRight className="ml-1 size-4" />
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </AuthGuard>
  );
}
