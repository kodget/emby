"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

const urlBase64ToUint8Array = (base64String: string) => {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding)
    .replace(/\-/g, "+")
    .replace(/_/g, "/");

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
};

export function usePushNotifications() {
  const [isSupported, setIsSupported] = useState(false);
  const [subscription, setSubscription] = useState<PushSubscription | null>(null);
  const [permission, setPermission] = useState<NotificationPermission>("default");
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if ("serviceWorker" in navigator && "PushManager" in window) {
      setIsSupported(true);
      setPermission(Notification.permission);
      
      navigator.serviceWorker.register("/sw.js")
        .then((registration) => {
          return registration.pushManager.getSubscription();
        })
        .then((sub) => {
          setSubscription(sub);
        })
        .catch((err) => {
          console.error("Service Worker registration failed:", err);
          setError(err);
        });
    }
  }, []);

  const subscribe = useCallback(async () => {
    if (!isSupported) return;
    try {
      const registration = await navigator.serviceWorker.ready;
      
      // Request permission if not granted
      const currentPermission = await Notification.requestPermission();
      setPermission(currentPermission);
      
      if (currentPermission !== "granted") {
        throw new Error("Notification permission denied");
      }

      const vapidPublicKey = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
      if (!vapidPublicKey) {
        throw new Error("VAPID public key not found");
      }

      const sub = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
      });

      setSubscription(sub);

      const subData = JSON.parse(JSON.stringify(sub));
      
      await api.post("/learning/notifications/subscribe/", {
        endpoint: subData.endpoint,
        p256dh: subData.keys.p256dh,
        auth: subData.keys.auth,
      });

      return true;
    } catch (err: any) {
      console.error("Push subscription error:", err);
      setError(err);
      return false;
    }
  }, [isSupported]);

  const unsubscribe = useCallback(async () => {
    if (!subscription) return;
    try {
      await subscription.unsubscribe();
      setSubscription(null);
      
      const subData = JSON.parse(JSON.stringify(subscription));
      await api.delete("/learning/notifications/subscribe/", {
        data: { endpoint: subData.endpoint }
      });
      
      return true;
    } catch (err: any) {
      console.error("Push unsubscription error:", err);
      setError(err);
      return false;
    }
  }, [subscription]);

  return {
    isSupported,
    permission,
    subscription,
    isSubscribed: !!subscription,
    subscribe,
    unsubscribe,
    error,
  };
}
