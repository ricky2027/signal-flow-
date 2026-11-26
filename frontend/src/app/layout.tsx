import type { Metadata } from 'next';
import './globals.css';
import { Shell } from '@/components/shell';
import { AuthGate } from '@/components/auth-gate';
export const metadata: Metadata = { title: { default: 'SIGNALFLOW — GTM intelligence', template: '%s · SIGNALFLOW' }, description: 'Evidence-backed prospect research and personalised outreach. Built for human review.' };
export default function RootLayout({ children }: {
    children: React.ReactNode;
}) {
    return <html lang="en"><body><Shell><AuthGate>{children}</AuthGate></Shell></body></html>;
}
