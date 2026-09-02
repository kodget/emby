"use client";

import { useEffect, useState } from "react";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { fetchNotifications, markRead } from "@/store/notifications-slice";
import { Bell, Check, X } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";

export function NotificationsDropdown() {
  const dispatch = useAppDispatch();
  const router = useRouter();
  const { items, unreadCount, status } = useAppSelector((state) => state.notifications);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    // Initial fetch handled by NotificationProvider
  }, []);

  const handleMarkAllRead = (e: React.MouseEvent) => {
    e.stopPropagation();
    dispatch(markRead());
  };

  const handleNotificationClick = (notification: any) => {
    if (!notification.read) {
      dispatch(markRead(notification.id));
    }
    if (notification.action_url) {
      setOpen(false);
      router.push(notification.action_url);
    }
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <motion.button
          type="button"
          whileTap={{ scale: 0.9 }}
          className="relative flex size-9 items-center justify-center rounded-full border border-border bg-card text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Notifications"
        >
          <Bell className="size-4" aria-hidden="true" />
          <AnimatePresence>
            {unreadCount > 0 && (
              <motion.div
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0, opacity: 0 }}
                className="absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full bg-destructive text-[10px] font-bold text-destructive-foreground"
              >
                {unreadCount > 9 ? "9+" : unreadCount}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.button>
      </DropdownMenuTrigger>
      
      <DropdownMenuContent align="end" className="w-80 max-h-[85vh] overflow-hidden flex flex-col p-0">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/30">
          <DropdownMenuLabel className="p-0 font-semibold text-sm">Notifications</DropdownMenuLabel>
          {unreadCount > 0 && (
            <Button 
              variant="ghost" 
              size="sm" 
              className="h-8 px-2 text-xs text-primary hover:text-primary"
              onClick={handleMarkAllRead}
            >
              <Check className="mr-1 size-3" />
              Mark all read
            </Button>
          )}
        </div>
        
        <div className="overflow-y-auto flex-1 p-1">
          {status === "loading" && items.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">Loading...</div>
          ) : items.length === 0 ? (
            <div className="p-8 text-center flex flex-col items-center justify-center space-y-3">
              <div className="flex size-12 items-center justify-center rounded-full bg-muted/50 text-muted-foreground">
                <Bell className="size-5 opacity-50" />
              </div>
              <p className="text-sm text-muted-foreground">You have no notifications right now.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-1">
              {items.slice(0, 10).map((n) => (
                <div
                  key={n.id}
                  onClick={() => handleNotificationClick(n)}
                  className={`flex cursor-pointer flex-col gap-1 rounded-md px-3 py-3 text-sm transition-colors hover:bg-muted/50 ${
                    !n.read ? "bg-primary/5" : ""
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className={`font-semibold ${!n.read ? "text-foreground" : "text-muted-foreground"}`}>
                      {n.title}
                    </span>
                    {!n.read && <div className="mt-1 size-2 shrink-0 rounded-full bg-primary" />}
                  </div>
                  {n.body && (
                    <span className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                      {n.body}
                    </span>
                  )}
                  <span className="text-[10px] text-muted-foreground/80 mt-1">
                    {formatDistanceToNow(new Date(n.created_at), { addSuffix: true })}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
        
        <div className="p-2 border-t border-border bg-muted/30">
          <Button
            variant="ghost"
            size="sm"
            className="w-full text-xs"
            onClick={() => {
              setOpen(false);
              router.push("/notifications");
            }}
          >
            View all notifications
          </Button>
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
