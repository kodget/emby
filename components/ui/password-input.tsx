"use client";
import { useState, type ComponentProps } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { Input } from './input';
import { cn } from '@/lib/utils';
export function PasswordInput({ className, ...props }: ComponentProps<'input'>) {
  const [visible, setVisible] = useState(false);
  return <div className="relative"><Input {...props} type={visible ? 'text' : 'password'} className={cn('min-h-11 pr-12', className)} />
    <button type="button" aria-label={visible ? 'Hide password' : 'Show password'} aria-pressed={visible} disabled={props.disabled}
      onClick={() => setVisible(value => !value)} className="absolute right-0 top-0 flex size-11 items-center justify-center rounded-r-md text-muted-foreground hover:text-foreground">
      {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
    </button></div>;
}
