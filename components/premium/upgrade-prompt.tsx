'use client';

import { Crown, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { useRouter } from 'next/navigation';

interface UpgradePromptProps {
  title: string;
  message: string;
  onClose?: () => void;
  showClose?: boolean;
}

export function UpgradePrompt({ title, message, onClose, showClose = true }: UpgradePromptProps) {
  const router = useRouter();

  return (
    <Card className="border-primary/50 bg-gradient-to-br from-primary/5 to-primary/10">
      {showClose && onClose && (
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-muted-foreground hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      )}
      <CardHeader>
        <div className="flex items-center gap-2 mb-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/20">
            <Crown className="h-4 w-4 text-primary" />
          </div>
          <CardTitle className="text-lg">{title}</CardTitle>
        </div>
        <CardDescription>{message}</CardDescription>
      </CardHeader>
      <CardFooter className="flex gap-2">
        <Button onClick={() => router.push('/premium')} className="flex-1">
          <Crown className="mr-2 h-4 w-4" />
          Upgrade to Premium
        </Button>
        {onClose && (
          <Button variant="outline" onClick={onClose}>
            Maybe Later
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}

interface UpgradeAlertProps {
  message: string;
  onUpgrade?: () => void;
  onDismiss?: () => void;
}

export function UpgradeAlert({ message, onUpgrade, onDismiss }: UpgradeAlertProps) {
  const router = useRouter();

  const handleUpgrade = () => {
    if (onUpgrade) {
      onUpgrade();
    } else {
      router.push('/premium');
    }
  };

  return (
    <div className="rounded-lg border border-primary/50 bg-primary/5 p-4">
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/20 flex-shrink-0">
          <Crown className="h-4 w-4 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium mb-2">{message}</p>
          <div className="flex gap-2">
            <Button size="sm" onClick={handleUpgrade}>
              Upgrade Now
            </Button>
            {onDismiss && (
              <Button size="sm" variant="ghost" onClick={onDismiss}>
                Dismiss
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
