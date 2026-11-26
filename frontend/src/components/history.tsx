'use client';
import { useCallback, useState } from 'react';
import Link from 'next/link';
import { Plus, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';
import type { RunSummary } from '@/lib/types';
import { useResource } from '@/hooks/use-resource';
import { RunTable } from './run-table';
import { ErrorNotice, Loading } from './feedback';
import { Button } from './ui/button';
export function History({ reviewOnly = false }: {
    reviewOnly?: boolean;
}) {
    const [extra, setExtra] = useState<RunSummary[]>([]);
    const [cursor, setCursor] = useState<string | null | undefined>();
    const [more, setMore] = useState(false);
    const [error, setError] = useState<Error>();
    const load = useCallback((signal: AbortSignal) => api.history(reviewOnly ? '?limit=50&status=awaiting_review' : '?limit=50', signal), [reviewOnly]);
    const resource = useResource(load);
    async function loadMore() {
        const next = cursor === undefined ? resource.data?.next_cursor : cursor;
        if (!next)
            return;
        setMore(true);
        setError(undefined);
        try {
            const page = await api.history(`?limit=50&cursor=${encodeURIComponent(next)}${reviewOnly ? '&status=awaiting_review' : ''}`);
            setExtra(items => [...items, ...page.items]);
            setCursor(page.next_cursor);
        }
        catch (e) {
            setError(e as Error);
        }
        finally {
            setMore(false);
        }
    }
    async function refresh() {
        setExtra([]);
        setCursor(undefined);
        await resource.refresh();
    }
    const runs = Array.from(new Map([...(resource.data?.items || []), ...extra].map(r => [r.id, r])).values());
    return <div className="page-content"><div className="page-heading"><div><div className="eyebrow">{reviewOnly ? 'THE HUMAN CHECKPOINT' : 'YOUR RESEARCH TRAIL'}</div><h1>{reviewOnly ? 'Review queue' : 'Research history'}<span className="heading-dot">.</span></h1><p>{reviewOnly ? 'Evidence-backed drafts, waiting for your judgment.' : 'Every prospect, signal and decision. Ready to revisit.'}</p></div><div className="inline-actions"><Button variant="outline" size="icon" aria-label="Refresh history" onClick={refresh}><RefreshCw size={17} className={resource.refreshing ? 'spin' : ''}/></Button><Button asChild><Link href="/research/new"><Plus size={17}/>New research</Link></Button></div></div>{resource.loading ? <Loading /> : <>{(resource.error || error) && <ErrorNotice error={(error || resource.error)!} retry={refresh}/>} {resource.data && <RunTable runs={runs} hasMore={!!(cursor === undefined ? resource.data.next_cursor : cursor)} loadMore={loadMore} loading={more} reviewOnly={reviewOnly}/>}</>}</div>;
}
