'use client';
import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, ArrowRight, Building2, Check, FileText, Globe2, Loader2, RefreshCw, ShieldCheck, TriangleAlert, UserRound } from 'lucide-react';
import { api } from '@/lib/api';
import type { QueuedRun } from '@/lib/types';
import { active, errorExplanations } from '@/lib/status';
import { dateTime, initials, safeUrl } from '@/lib/utils';
import { useResource } from '@/hooks/use-resource';
import { useRunEvents } from '@/hooks/use-run-events';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { ErrorNotice, Loading } from './feedback';
import { StatusBadge } from './status-badge';
import { StageTimeline, ExecutionPanel } from './execution';
import { EvidencePanel, SignalsPanel } from './evidence';
import { IdentityChecksPanel } from './identity-checks';
import { DraftReview } from './draft-review';
export function RunDetailScreen({ id }: {
    id: string;
}) {
    const load = useCallback((signal: AbortSignal) => api.detail(id, signal), [id]);
    const resource = useResource(load);
    const run = resource.data;
    const { events, connection, notices, reconnect } = useRunEvents(id, run, resource.refresh);
    const [tab, setTab] = useState('research');
    const [busy, setBusy] = useState(false);
    const [actionError, setActionError] = useState<Error>();
    const router = useRouter();
    const retryKey = useRef<string | undefined>(undefined);
    useEffect(() => {
        if (!run || !active(run.status))
            return;
        const timer = setInterval(() => {
            if (!document.hidden)
                void resource.refresh();
        }, 4000);
        return () => clearInterval(timer);
    }, [run?.status, resource.refresh]);
    async function retry() {
        setBusy(true);
        setActionError(undefined);
        try {
            retryKey.current ??= crypto.randomUUID();
            const queued = await api.action(id, 'retry', {}, retryKey.current) as QueuedRun;
            router.push(`/runs/${queued.run_id}`);
        }
        catch (e) {
            setActionError(e as Error);
            setBusy(false);
        }
    }
    if (resource.loading)
        return <Loading label="Loading research and execution history…"/>;
    if (!run)
        return <div className="page-content"><Link href="/runs" className="back-link"><ArrowLeft size={15}/>Research history</Link><ErrorNotice error={resource.error || new Error('Research could not be loaded.')} retry={resource.refresh}/></div>;
    const errorCode = typeof run.error?.code === 'string' ? run.error.code : '';
    const abstained = ['insufficient_information', 'conflicting_evidence', 'no_relevant_signal'].includes(run.status);
    const tabs = [{ id: 'research', label: 'Research', count: run.signals.length }, { id: 'evidence', label: 'Evidence', count: run.sources.length }, { id: 'draft', label: 'Outreach draft', count: run.drafts.length }, { id: 'execution', label: 'Execution log', count: events.length }];
    return <div className="page-content detail-page"><Link href="/runs" className="back-link"><ArrowLeft size={15}/>Research history</Link><div className="run-heading"><span className="person-avatar large">{initials(run.prospect_name)}</span><div className="run-title"><div className="eyebrow">PROSPECT INTELLIGENCE <span>/</span> {run.id.slice(0, 8)}</div><h1>{run.prospect_name}</h1><p><UserRound size={14}/>{run.input.designation}<span className="meta-separator">/</span><Building2 size={14}/>{run.company_name}</p></div><div className="run-heading-actions"><StatusBadge status={run.status}/><Button size="icon" variant="outline" onClick={resource.refresh} disabled={resource.refreshing} aria-label="Refresh run"><RefreshCw size={16} className={resource.refreshing ? 'spin' : ''}/></Button></div></div>{resource.error && <ErrorNotice error={resource.error} retry={resource.refresh}/>}{actionError && <ErrorNotice error={actionError}/>}
 {run.status === 'failed' && <div className="outcome-notice failed" role="alert"><div className="outcome-notice-icon"><TriangleAlert size={21}/></div><div><strong>Research couldn’t be completed</strong><p>{errorExplanations[errorCode] || 'The backend reported a research failure. Review the execution log for the recorded reason.'}</p><small>Backend reason: <code>{errorCode || 'not provided'}</code> · {run.sources.length} sources · {run.drafts.length} drafts</small>{Array.isArray(run.error?.findings) && <ul>{(run.error.findings as string[]).map((f, i) => <li key={i}>{f}</li>)}</ul>}</div><Button variant="outline" size="sm" onClick={retry} disabled={busy}>{busy ? <Loader2 size={15} className="spin"/> : <RefreshCw size={15}/>}Retry research</Button></div>}
 {abstained && <div className="outcome-notice abstained"><div className="outcome-notice-icon"><ShieldCheck size={21}/></div><div><strong>{run.status === 'insufficient_information' ? 'Not enough evidence to personalise' : run.status === 'conflicting_evidence' ? 'Conflicting evidence needs attention' : 'No sufficiently relevant signal'}</strong><p>{errorExplanations[run.status]}</p><small>Outcome: {run.outcome_reason?.replaceAll('_', ' ') || run.status.replaceAll('_', ' ')} · No new draft generated.</small></div><Button asChild variant="outline" size="sm"><Link href="/research/new">New research<ArrowRight size={14}/></Link></Button></div>}
 {connection === 'reconnecting' && <div className="stream-warning" role="status"><RefreshCw size={15}/>Live connection interrupted. Reconnecting; saved results remain visible.<Button variant="ghost" size="sm" onClick={reconnect}>Reconnect now</Button></div>}
 <div className="run-context-strip"><span><Globe2 size={14}/>{run.input.company_website ? <a href={safeUrl(run.input.company_website)} target="_blank" rel="noopener noreferrer">{run.input.company_website.replace(/^https?:\/\//, '')}</a> : 'Website not provided'}</span><span>Created {dateTime(run.created_at)}</span><span><ShieldCheck size={14}/>{run.sources.length} sources</span><span><FileText size={14}/>{run.drafts.length} draft versions</span>{run.parent_run_id && <Link href={`/runs/${run.parent_run_id}`}>View original run ↗</Link>}</div>
 <div className="detail-layout"><aside className="detail-sidebar"><StageTimeline run={run} events={events} connection={connection}/><Card className="offer-context"><span className="eyebrow">OFFER CONTEXT</span><h3>{run.input.product_service}</h3><p>{run.input.value_proposition}</p><div><ShieldCheck size={14}/>Relevance is evaluated against this offer.</div></Card></aside><div className="detail-main"><div className="tabs" role="tablist" aria-label="Research detail sections">{tabs.map((item, index) => <button key={item.id} id={`tab-${item.id}`} role="tab" aria-selected={tab === item.id} aria-controls={`panel-${item.id}`} tabIndex={tab === item.id ? 0 : -1} className={tab === item.id ? 'active' : ''} onClick={() => setTab(item.id)} onKeyDown={e => {
        if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
            e.preventDefault();
            const next = tabs[(index + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
            setTab(next.id);
            document.getElementById(`tab-${next.id}`)?.focus();
        }
    }}>{item.label}<span>{item.count}</span></button>)}</div><div id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} className="tab-panel">{tab === 'research' && <>{run.warnings.map((warning, i) => <div className="warning-note" key={i}><TriangleAlert size={15}/>{warning === 'role_currentness_unverified_role_claims_excluded' ? 'Current employment is unverified. Unverified role claims are excluded from scoring and outreach.' : warning}</div>)}<IdentityChecksPanel run={run}/><SignalsPanel run={run}/><Card className="research-summary"><span className="eyebrow">FROM SIGNAL TO CONVERSATION</span><h3>{active(run.status) ? 'Research is in progress.' : run.drafts.length ? 'Your outreach, grounded in context.' : 'Evidence sets the boundary.'}</h3><p>{active(run.status) ? 'Stages update as the worker commits results. If this stays queued, check that the backend worker is running.' : run.drafts.length ? 'Open the draft to review its claims and supporting evidence before recording a decision.' : 'This run has not produced an outreach draft. Review the evidence and execution log to understand the outcome.'}</p><Button size="sm" variant="outline" onClick={() => setTab(run.drafts.length ? 'draft' : 'execution')}>{run.drafts.length ? 'Review outreach draft' : 'View execution log'}<ArrowRight size={14}/></Button></Card></>}{tab === 'evidence' && <EvidencePanel run={run}/>} <div hidden={tab !== 'draft'}><DraftReview run={run} refresh={resource.refresh}/></div> {tab === 'execution' && <ExecutionPanel run={run} events={events} notices={notices}/>}</div></div></div></div>;
}
