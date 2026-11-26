import Link from 'next/link';
import { Button } from '@/components/ui/button';
export default function NotFound() {
    return <div className="page-content empty-state"><h1>Page not found.</h1><p>Return to your workspace to find a research run.</p><Button asChild><Link href="/">Back to overview</Link></Button></div>;
}
