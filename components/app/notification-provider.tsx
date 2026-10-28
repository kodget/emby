"use client";

import { useEffect, useRef } from "react";
import { useDispatch, useSelector } from "react-redux";
import { RootState, AppDispatch } from "@/store/store";
import { addNotification, fetchNotifications } from "@/store/notifications-slice";
import confetti from "canvas-confetti";

import { useToast } from "@/hooks/use-toast";

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const dispatch = useDispatch<AppDispatch>();
  const userId = useSelector((state: RootState) => state.user.id);
  const ws = useRef<WebSocket | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    if (!userId) return;

    // Fetch initial list
    dispatch(fetchNotifications(false));

    // Determine WebSocket URL
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    // Replace http:// or https:// with ws:// or wss://, taking care of the trailing slash
    const baseWsUrl = apiUrl.replace(/^http/, 'ws').replace(/\/$/, '');
    const wsUrl = `${baseWsUrl}/ws/notifications/`;
    let stopped = false;
    let reconnect: ReturnType<typeof setTimeout> | undefined;
    let retryDelay = 1000;
    let failedConnections = 0;
    const seen = new Set<string>();
    // The durable inbox also catches up after a dropped socket or a sleeping tab.
    const poll = setInterval(() => { if (document.visibilityState === 'visible') dispatch(fetchNotifications(false)); }, 60000);

    // Connect to WebSocket
    const connect = () => {
    if (stopped) return;
    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      failedConnections = 0;
      retryDelay = 1000;
      dispatch(fetchNotifications(false));
      // Send auth token to authenticate connection if needed
      const token = sessionStorage.getItem("token");
      ws.current?.send(JSON.stringify({ type: "auth", token }));
    };

    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "notification") {
          if (stopped || seen.has(data.data.id)) return;
          seen.add(data.data.id);
          dispatch(addNotification(data.data));
          
          const isGamification = data.data.type === "BADGE_EARNED" || data.data.type === "ACHIEVEMENT";
          
          if (isGamification) {
            // Fire confetti for gamification events!
            const duration = 3 * 1000;
            const animationEnd = Date.now() + duration;
            const defaults = { startVelocity: 30, spread: 360, ticks: 60, zIndex: 100 };

            const randomInRange = (min: number, max: number) => Math.random() * (max - min) + min;

            const interval = setInterval(function() {
              const timeLeft = animationEnd - Date.now();

              if (timeLeft <= 0) {
                return clearInterval(interval);
              }

              const particleCount = 50 * (timeLeft / duration);
              confetti({
                ...defaults, particleCount,
                origin: { x: randomInRange(0.1, 0.3), y: Math.random() - 0.2 }
              });
              confetti({
                ...defaults, particleCount,
                origin: { x: randomInRange(0.7, 0.9), y: Math.random() - 0.2 }
              });
            }, 250);
          }
          
          // Pop a subtle toast, or a celebratory one
          toast({
            title: isGamification ? "🎉 " + data.data.title : data.data.title,
            description: data.data.body || undefined,
            duration: isGamification ? 6000 : 4000,
          });
        }
      } catch (err) {
        console.error("Failed to parse notification message", err);
      }
    };

    ws.current.onerror = (error) => {
      console.error("Notification WebSocket error", error);
    };
    ws.current.onclose = () => {
      if (stopped) return;
      // WSGI deployments have no socket endpoint. Keep the durable inbox
      // polling instead of sending failing handshakes indefinitely.
      failedConnections++;
      if (failedConnections >= 3) return;
      reconnect = setTimeout(connect, retryDelay);
      retryDelay = Math.min(30000, retryDelay * 2);
    };
    };
    connect();

    return () => {
      stopped = true;
      clearTimeout(reconnect);
      clearInterval(poll);
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [userId, dispatch]);

  return <>{children}</>;
}
