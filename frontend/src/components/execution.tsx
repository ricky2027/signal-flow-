import { Check, CheckCheck, ChevronDown, Circle, Loader2, Radio, RefreshCw, TriangleAlert, X } from 'lucide-react';
import type { RunDetail, RunEvent, ProviderCall } from '@/lib/types';
import { dateTime, safeUrl } from '@/lib/utils';
import { active, stages, stageState } from '@/lib/status';
import { Card } from './ui/card';
export function StageTimeline({ run, events, connection }: {
    run: RunDetail;
    events: RunEvent[];
    connection: string;
}) {
    const cycleStart = events.map(e => e.type).lastIndexOf('run.queued');
    const cycle = cycleStart >= 0 ? events.slice(cycleStart) : events;
    const reused = cycle[0]?.payload.kind === 'regenerate';
    return <Card className="stage-card"><div className="stage-title"><span className="eyebrow">RESEARCH WORKFLOW</span><span className={`live-indicator ${connection === 'connected' && active(run.status) ? 'live' : ''}`}><i />{connection === 'synced' ? 'History synced' : connection === 'reconnecting' ? 'Reconnecting' : connection === 'connected' ? 'Connected' : 'Connecting'}</span></div><ol className="stage-list">{stages.map((stage, index) => {
        const recorded = reused && ['validate', 'research', 'qualify_evidence'].includes(stage.id) ? 'reused' : stageState(stage.id, cycle, run);
        // Historical runs predate explicit gate metadata, but this outcome at
        // the evaluation node also exits before candidate generation.
        const state = stage.id === 'evaluate_signals' && recorded === 'complete' && !run.signals.length && ['insufficient_information', 'conflicting_evidence'].includes(run.status) ? 'blocked' : recorded;
        return <li key={stage.id} className={`stage-item ${state === 'blocked' || state === 'skipped' ? 'stopped' : state}`}><span className="stage-node">{state === 'complete' ? <Check size={14}/> : state === 'active' ? <Loader2 size={15} className="spin"/> : state === 'failed' ? <X size={14}/> : state === 'reused' ? <RefreshCw size={13}/> : <span>{index + 1}</span>}</span><div><strong>{stage.label}</strong><p>{state === 'reused' ? 'Using existing evidence' : stage.description}</p><small>{state === 'blocked' ? 'Evidence gate blocked scoring' : state === 'skipped' ? 'Skipped after abstention' : state === 'complete' ? 'Completed' : state === 'active' ? 'In progress' : state === 'failed' ? 'Failed' : state === 'stopped' ? 'Stopped before completion' : state === 'reused' ? 'Reused' : 'Not started'}</small></div></li>;
    })}</ol><div className="stage-foot"><CheckCheck size={16}/><p>Progress reflects committed backend events.</p></div></Card>;
}
const eventTitle: Record<string, string> = { 'run.queued': 'Research queued', 'stage.started': 'Stage started', 'stage.completed': 'Stage completed', 'research.updated': 'Research results saved', 'stage.result': 'Stage output saved', 'draft.created': 'Draft version created', 'run.status_changed': 'Run status changed', 'run.failed': 'Research failed' };
export function ExecutionPanel({ run, events, notices }: {
    run: RunDetail;
    events: RunEvent[];
    notices: Array<{
        at: string;
        text: string;
    }>;
}) {
    const calls = run.provider_calls as ProviderCall[];
    return <div className="execution-panel"><Card className="event-card"><div className="section-mini-heading"><h3>Execution timeline</h3><span>{events.length} persisted events</span></div>{events.length ? <ol className="event-list">{events.map(event => <li key={event.sequence} className={event.type === 'run.failed' ? 'event-failed' : ''}><span className="event-node">{event.type === 'run.failed' ? <TriangleAlert size={13}/> : event.type === 'stage.completed' ? <Check size={13}/> : <Circle size={9}/>}</span><div><strong>{eventTitle[event.type] || event.type}</strong><p>{event.stage?.replaceAll('_', ' ')}{typeof event.payload.artifact === 'string' ? ` · ${event.payload.artifact.replaceAll('_', ' ')}` : ''}{typeof event.payload.status === 'string' ? ` · ${event.payload.status.replaceAll('_', ' ')}` : ''}{typeof event.payload.code === 'string' ? ` · ${event.payload.code}` : ''}{typeof event.payload.version === 'number' ? ` · version ${event.payload.version}` : ''}</p></div><time>{dateTime(event.occurred_at)}</time></li>)}</ol> : <p className="quiet-empty">Waiting to receive committed execution events.</p>}</Card><Card className="provider-card"><div className="section-mini-heading"><h3>Provider requests & retries</h3><span>{calls.filter(c => c.status !== 'tool_activity').length} attempts recorded</span></div>{calls.length ? <div className="provider-list">{calls.map((call, index) => <div key={index} className={`provider-row ${call.status === 'failed' ? 'is-failure' : ''}`}><span className="provider-symbol">{call.status === 'failed' ? <TriangleAlert size={16}/> : <Radio size={16}/>}</span><div><strong>{call.stage?.replaceAll('_', ' ') || 'Provider request'}{call.attempt ? ` · attempt ${call.attempt}` : ''}</strong><p>{call.error_code || call.status}{call.http_status ? ` · HTTP ${call.http_status}` : ''}{typeof call.latency_ms === 'number' ? ` · ${call.latency_ms} ms` : ''}</p>{call.model && <small>{call.model}</small>}{call.provider_request_id && <small className="request-id">{call.provider_request_id}</small>}</div></div>)}</div> : <p className="quiet-empty">No provider calls have been recorded.</p>}</Card>{notices.length > 0 && <Card className="connection-notices"><div className="section-mini-heading"><h3>Browser connection log</h3><span>Local notices · not backend events</span></div>{notices.map((notice, i) => <div key={i}><time>{dateTime(notice.at)}</time><p>{notice.text}</p></div>)}</Card>}<details className="run-metadata"><summary>Run metadata<ChevronDown size={14}/></summary><dl><dt>Run ID</dt><dd>{run.id}</dd><dt>Policy</dt><dd>{run.policy_version}</dd><dt>Models</dt><dd>{Object.entries(run.model_versions).map(([k, v]) => `${k}: ${v}`).join(' · ')}</dd></dl></details></div>;
}
