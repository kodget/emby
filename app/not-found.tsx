import Link from 'next/link';
import { Button } from '@/components/ui/button';
export default function NotFound() {
  return <main className="mx-auto max-w-xl px-6 py-24 text-center">
    <p className="text-sm font-semibold text-primary">404 · Page not found</p><h1 className="mt-4 text-3xl">Let’s get you back to studying.</h1>
    <p className="mt-4 text-muted-foreground">This link may have moved. Search your library or return to Emby.</p>
    <div className="mt-8 flex flex-wrap justify-center gap-3"><Button asChild><Link href="/search">Search library</Link></Button><Button asChild variant="outline"><Link href="/">Go home</Link></Button></div>
  </main>;
}
