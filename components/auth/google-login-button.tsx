"use client";

import { useState, useEffect, useRef } from 'react';
import { Loader2 } from "lucide-react";
import { authApi } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

interface GoogleLoginButtonProps {
  onSuccess: (user: any, tokens: any, isNewUser: boolean) => void;
  className?: string;
}

declare global {
  interface Window {
    google: any;
    handleGoogleCallback: (response: any) => void;
  }
}

export function GoogleLoginButton({ onSuccess, className = "" }: GoogleLoginButtonProps) {
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();
  const buttonRef = useRef<HTMLDivElement>(null);
  const initialized = useRef(false);

  useEffect(() => {
    const initializeGoogle = () => {
      if (!window.google || initialized.current) return;

      try {
        console.log('Initializing Google Sign-In...');
        
        // Define callback function globally so Google can access it
        window.handleGoogleCallback = async (response: any) => {
          console.log('Google callback triggered');
          console.log('Response object:', response);
          console.log('Credential:', response.credential ? 'Present' : 'Missing');
          
          setLoading(true);
          
          try {
            console.log('Sending credential to backend...');
            console.log('API URL:', process.env.NEXT_PUBLIC_API_URL);
            
            const result = await authApi.googleLogin(response.credential);
            console.log('Backend response:', result);
            
            // Call the success handler
            onSuccess(result.user, result.tokens, result.is_new_user);
          } catch (error: any) {
            console.error('Google login error:', error);
            console.error('Error response:', error.response?.data);
            console.error('Error status:', error.response?.status);
            
            toast({
              title: 'Google Sign-In failed',
              description: error.response?.data?.error || 'Please try again.',
              variant: 'destructive',
            });
            setLoading(false);
          }
        };

        window.google.accounts.id.initialize({
          client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID,
          callback: window.handleGoogleCallback,
          auto_select: false,
        });

        // Render the button
        if (buttonRef.current) {
          window.google.accounts.id.renderButton(buttonRef.current, {
            theme: 'outline',
            size: 'large',
            width: buttonRef.current.offsetWidth || 300,
            text: 'continue_with',
            shape: 'rectangular',
          });
          console.log('Google button rendered');
        }

        initialized.current = true;
      } catch (error) {
        console.error('Failed to initialize Google Sign-In:', error);
        toast({
          title: 'Initialization Error',
          description: 'Failed to load Google Sign-In. Please refresh the page.',
          variant: 'destructive',
        });
      }
    };

    // Wait for Google script to load
    if (window.google) {
      initializeGoogle();
    } else {
      const checkGoogle = setInterval(() => {
        if (window.google) {
          clearInterval(checkGoogle);
          initializeGoogle();
        }
      }, 100);

      // Cleanup
      return () => clearInterval(checkGoogle);
    }

    // Cleanup callback on unmount
    return () => {
      if (window.handleGoogleCallback) {
        delete window.handleGoogleCallback;
      }
    };
  }, [onSuccess, toast]);

  return (
    <div className="w-full">
      {loading && (
        <div className="flex items-center justify-center py-2">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span className="ml-2 text-sm">Signing in...</span>
        </div>
      )}
      <div ref={buttonRef} className={loading ? 'hidden' : 'w-full'} />
    </div>
  );
}
