import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Shell } from '@/components/shell';
import { AuthGate } from '@/components/auth-gate';
const inter = Inter({ subsets: ['latin'], display: 'swap', variable: '--font-inter' });
export const metadata: Metadata = { title: { default: 'SIGNALFLOW — GTM intelligence', template: '%s · SIGNALFLOW' }, description: 'Evidence-backed prospect research and personalised outreach. Built for human review.' };
export default function RootLayout({ children }: {
    children: React.ReactNode;
}) {
    return <html lang="en" className={inter.variable}><body><Shell><AuthGate>{children}</AuthGate></Shell></body></html>;
}
