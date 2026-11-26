'use client';
import { AlertCircle, ArrowRight, Loader2, Radio, RefreshCw } from 'lucide-react';
import { ApiError } from '@/lib/api';
import { Button } from './ui/button';
import type { ReactNode } from 'react';
export function Loading({ label = 'Loading your workspace…' }: {
    label?: string;
}) {
    return <div className="loading-state" role="status"><Loader2 className="spin" size={22}/><p>{label}</p></div>;
}
export function ErrorNotice({ error, retry }: {
    error: Error;
    retry?: () => void;
}) {
    return <div className="error-notice" role="alert"><AlertCircle size={20}/><div><strong>{error instanceof ApiError && error.status === 401 ? 'Your session has expired' : 'We couldn’t complete that request'}</strong><p>{error.message}</p>{error instanceof ApiError && <small>{error.code}{error.requestId ? ` · Request ${error.requestId.slice(0, 8)}` : ''}</small>}</div>{retry && <Button variant="outline" size="sm" onClick={retry}><RefreshCw size={14}/>Try again</Button>}{error instanceof ApiError && error.status === 401 && <Button variant="outline" size="sm" onClick={() => window.location.reload()}>Sign in<ArrowRight size={14}/></Button>}</div>;
}
export function EmptyState({ title, description, action, icon }: {
    title: string;
    description: string;
    action?: ReactNode;
    icon?: ReactNode;
}) {
    return <div className="empty-state"><div className="empty-icon">{icon || <Radio size={26}/>}</div><h3>{title}</h3><p>{description}</p>{action}</div>;
}
