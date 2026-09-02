import { cn } from "@/lib/utils";

type Props = {
  src: string;
  alt: string;
  caption?: string;
  className?: string;
};

export function SlideViewer({ src, alt, caption, className }: Props) {
  return (
    <div
      className={cn(
        "flex-1 flex flex-col min-h-0 w-full relative group",
        className,
      )}
    >
      <img 
        src={src} 
        alt={alt} 
        className="w-full h-full object-contain drop-shadow-sm" 
        loading="lazy" 
      />
      {caption && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-background/80 backdrop-blur-md px-3 py-1.5 rounded-full border border-border text-[11px] text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
          {caption}
        </div>
      )}
    </div>
  );
}
