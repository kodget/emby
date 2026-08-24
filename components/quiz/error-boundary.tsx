"use client";

import React from "react";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class QuizErrorBoundary extends React.Component<
  React.PropsWithChildren<{}>,
  ErrorBoundaryState
> {
  constructor(props: React.PropsWithChildren<{}>) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      error: error,
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("Quiz Error Boundary caught an error:", error, errorInfo);
    
    // Log to external service in production
    if (process.env.NODE_ENV === "production") {
      // Could send to Sentry, LogRocket, etc.
      console.error("Production error in quiz system:", {
        error: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
        url: window.location.href,
      });
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  handleGoHome = () => {
    window.location.href = "/dashboard";
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-background p-4">
          <Card className="w-full max-w-md">
            <CardHeader className="text-center">
              <div className="w-16 h-16 rounded-full bg-rose-100 flex items-center justify-center mx-auto mb-4">
                <AlertTriangle className="w-8 h-8 text-rose-600" />
              </div>
              <CardTitle className="text-xl">Something went wrong</CardTitle>
            </CardHeader>
            <CardContent className="text-center space-y-4">
              <p className="text-muted-foreground">
                We encountered an unexpected error. Your progress has been saved automatically.
              </p>
              
              {process.env.NODE_ENV === "development" && this.state.error && (
                <details className="text-left">
                  <summary className="cursor-pointer text-sm text-muted-foreground hover:text-foreground">
                    Error Details (Development)
                  </summary>
                  <pre className="mt-2 p-2 bg-muted rounded text-xs overflow-auto max-h-32">
                    {this.state.error.message}
                    {this.state.error.stack && `\n\n${this.state.error.stack}`}
                  </pre>
                </details>
              )}
              
              <div className="flex flex-col sm:flex-row gap-2">
                <Button onClick={this.handleRetry} variant="outline" className="gap-2">
                  <RefreshCw className="w-4 h-4" />
                  Try Again
                </Button>
                <Button onClick={this.handleGoHome} className="gap-2">
                  <Home className="w-4 h-4" />
                  Go to Dashboard
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}

// Hook for retry logic in components
export const useRetryLogic = () => {
  const [retryCount, setRetryCount] = React.useState(0);
  const [isRetrying, setIsRetrying] = React.useState(false);

  const retry = React.useCallback(async (fn: () => Promise<void>, maxRetries = 3) => {
    if (retryCount >= maxRetries) {
      throw new Error(`Max retry attempts (${maxRetries}) exceeded`);
    }

    setIsRetrying(true);
    try {
      await fn();
      setRetryCount(0); // Reset on success
    } catch (error) {
      setRetryCount(prev => prev + 1);
      
      // Exponential backoff
      const delay = Math.min(1000 * Math.pow(2, retryCount), 5000);
      await new Promise(resolve => setTimeout(resolve, delay));
      
      throw error;
    } finally {
      setIsRetrying(false);
    }
  }, [retryCount]);

  return { retry, retryCount, isRetrying, maxRetries: 3 };
};

// Auto-save hook with offline queue
export const useAutoSave = () => {
  const [saveQueue, setSaveQueue] = React.useState<Array<() => Promise<void>>>([]);
  const [isOnline, setIsOnline] = React.useState(navigator.onLine);

  React.useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  // Process queue when online
  React.useEffect(() => {
    if (isOnline && saveQueue.length > 0) {
      (async () => {
        const queue = [...saveQueue];
        setSaveQueue([]);
        
        for (const saveFn of queue) {
          try {
            await saveFn();
          } catch (error) {
            console.error("Failed to process queued save:", error);
            // Re-queue on failure
            setSaveQueue(prev => [...prev, saveFn]);
          }
        }
      })();
    }
  }, [isOnline, saveQueue]);

  const queueSave = React.useCallback((saveFn: () => Promise<void>) => {
    if (isOnline) {
      // Try immediate save
      saveFn().catch(error => {
        console.error("Auto-save failed, queuing for retry:", error);
        setSaveQueue(prev => [...prev, saveFn]);
      });
    } else {
      // Queue for when online
      setSaveQueue(prev => [...prev, saveFn]);
    }
  }, [isOnline]);

  return { queueSave, isOnline, queueLength: saveQueue.length };
};