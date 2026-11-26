'use client';
import { useEffect, useState } from 'react';
import { Check, Copy, FileText, Loader2, Pencil, RefreshCw, Save, ShieldCheck, ThumbsDown, TriangleAlert } from 'lucide-react';
import type { RunDetail, DraftView, QueuedRun } from '@/lib/types';
import { api, ApiError } from '@/lib/api';
import { dateTime, safeUrl } from '@/lib/utils';
import { active } from '@/lib/status';
import { Button } from './ui/button';
import { Input, Textarea } from './ui/input';
import { Card } from './ui/card';
import { EmptyState, ErrorNotice } from './feedback';
export function DraftReview({ run, refresh }: {
    run: RunDetail;
    refresh: () => Promise<void>;
}) {
    const [selectedVersion, setSelectedVersion] = useState<number>();
    useEffect(() => setSelectedVersion(undefined), [run.current_draft_id]);
    const current = run.drafts.find(d => d.id === run.current_draft_id) || run.drafts.at(-1);
    const selected = selectedVersion ? run.drafts.find(d => d.version === selectedVersion) : current;
    return <div className="draft-review"><div className="section-heading compact"><div><h2>Outreach draft</h2><p>Personalised by evidence. Finalised by you.</p></div>{run.drafts.length > 0 && <select aria-label="Draft version" value={selected?.version || ''} onChange={e => setSelectedVersion(Number(e.target.value))}>{run.drafts.map(d => <option key={d.id} value={d.version}>Version {d.version}{d.id === run.current_draft_id ? ' · current' : ''}</option>)}</select>}</div>{!selected ? <Card><EmptyState icon={<FileText size={26}/>} title="No draft generated" description={active(run.status) ? 'A draft will appear only after the evidence and quality checks pass.' : 'This run has no outreach draft. No email was created or sent.'}/></Card> : <DraftEditor key={selected.id} draft={selected} run={run} isCurrent={selected.id === run.current_draft_id} refresh={refresh}/>}<div className="review-safety"><ShieldCheck size={17}/><p><strong>You stay in control.</strong> Approving records your decision. SIGNALFLOW never sends an email automatically.</p></div>{run.reviews.length > 0 && <Card className="review-history"><h3>Review history</h3>{run.reviews.map(review => <div key={review.id}><span className={`decision-icon ${review.action}`}>{review.action === 'approved' ? <Check size={14}/> : <ThumbsDown size={14}/>}</span><div><strong>{review.action === 'approved' ? 'Approved' : 'Rejected'} · version {run.drafts.find(d => d.id === review.draft_id)?.version ?? 'unknown'}</strong>{review.reason && <p>{review.reason}</p>}</div><time>{dateTime(review.created_at)}</time></div>)}</Card>}</div>;
}
function DraftEditor({ draft, run, isCurrent, refresh }: {
    draft: DraftView;
    run: RunDetail;
    isCurrent: boolean;
    refresh: () => Promise<void>;
}) {
    const [subject, setSubject] = useState(draft.subject);
    const [body, setBody] = useState(draft.body);
    const [editing, setEditing] = useState(false);
    const [busy, setBusy] = useState('');
    const [error, setError] = useState<Error>();
    const [notice, setNotice] = useState('');
    const [instructions, setInstructions] = useState('');
    const [reason, setReason] = useState('');
    const [confirm, setConfirm] = useState<'reject' | 'regenerate' | null>(null);
    const dirty = subject !== draft.subject || body !== draft.body;
    const canAct = isCurrent && ['awaiting_review', 'approved', 'rejected'].includes(run.status);
    const approved = isCurrent && run.status === 'approved';
    useEffect(() => {
        if (!dirty)
            return;
        const guard = (event: BeforeUnloadEvent) => {
            event.preventDefault();
            event.returnValue = '';
        };
        window.addEventListener('beforeunload', guard);
        return () => window.removeEventListener('beforeunload', guard);
    }, [dirty]);
    async function action(name: 'save' | 'approve' | 'reject' | 'regenerate') {
        if (busy)
            return;
        setBusy(name);
        setError(undefined);
        setNotice('');
        try {
            if (name === 'save') {
                await api.edit(run.id, draft.version, subject.trim(), body.trim());
                setEditing(false);
                setNotice('New version saved. Review is required again.');
            }
            else {
                await api.action(run.id, name, { draft_version: draft.version, ...(name === 'reject' ? { reason: reason.trim() || null } : {}), ...(name === 'regenerate' ? { instructions: instructions.trim() || null } : {}) }, name === 'regenerate' ? crypto.randomUUID() : undefined);
                setNotice(name === 'approve' ? 'Draft approved. No email was sent.' : name === 'reject' ? 'Draft rejected. Your decision is recorded.' : 'Regeneration queued. A new version will need your review.');
            }
            setConfirm(null);
            await refresh();
        }
        catch (e) {
            setError(e as Error);
            if (e instanceof ApiError && e.code === 'unsupported_content')
                await refresh();
        }
        finally {
            setBusy('');
        }
    }
    async function copy() {
        try {
            await navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`);
            setNotice('Draft copied to clipboard.');
        }
        catch {
            setError(new Error('Clipboard access was blocked. Select and copy the text manually.'));
        }
    }
    const refs = draft.claim_refs.flatMap(ref => ref.claim_ids);
    const supporting = run.claims.filter(c => refs.includes(c.id));
    return <><Card className="email-card"><div className="email-toolbar"><div><span className="email-icon"><FileText size={16}/></span><strong>Email draft</strong><span className="version-tag">v{draft.version}</span></div><div className="inline-actions"><Button variant="ghost" size="sm" onClick={copy}><Copy size={14}/>Copy</Button>{canAct && <Button variant="outline" size="sm" onClick={() => {
        setEditing(!editing);
        if (editing) {
            setSubject(draft.subject);
            setBody(draft.body);
        }
    }} disabled={!!busy}><Pencil size={14}/>{editing ? 'Cancel edit' : 'Edit draft'}</Button>}</div></div>{(!isCurrent || !canAct) && <div className="archived-draft"><TriangleAlert size={15}/>{!isCurrent ? 'Historical version · read only' : `Previous draft retained · this run is ${run.status.replaceAll('_', ' ')}`}</div>}{approved && <div className="approved-banner"><ShieldCheck size={17}/>Approved for manual use. No email has been sent.</div>}{editing ? <div className="email-fields"><label htmlFor="draft-subject">Subject</label><Input id="draft-subject" value={subject} maxLength={200} onChange={e => setSubject(e.target.value)} disabled={!!busy}/><label htmlFor="draft-body">Email body</label><Textarea id="draft-body" value={body} maxLength={5000} rows={12} onChange={e => setBody(e.target.value)} disabled={!!busy}/><p className="field-hint">Saving creates a new version and clears previous approval. Claims are revalidated when you approve.</p><Button onClick={() => action('save')} disabled={!dirty || !subject.trim() || !body.trim() || !!busy}>{busy === 'save' ? <Loader2 className="spin" size={15}/> : <Save size={15}/>}Save new version</Button></div> : <><div className="email-subject"><span>Subject</span><strong>{draft.subject}</strong></div><div className="email-body">{draft.body}</div></>}<div className="email-validation"><ShieldCheck size={15}/><span>{dirty ? 'Unsaved changes · approval unavailable' : draft.validation_status === 'valid' ? 'Evidence validation passed' : draft.validation_status === 'invalid' ? 'Evidence validation requires attention' : 'Pending evidence validation'}</span></div>{draft.validation_findings.length > 0 && <ul className="validation-findings">{draft.validation_findings.map((f, i) => <li key={i}>{f}</li>)}</ul>}</Card>{error && <ErrorNotice error={error}/>} {notice && <div className="success-notice" role="status"><Check size={17}/>{notice}</div>}{canAct && <div className="review-actions"><div className="inline-actions"><Button variant="outline" disabled={!!busy || dirty || editing} onClick={() => setConfirm(confirm === 'regenerate' ? null : 'regenerate')}><RefreshCw size={15}/>Regenerate</Button><Button variant="ghost" disabled={!!busy || dirty || editing} onClick={() => setConfirm(confirm === 'reject' ? null : 'reject')}><ThumbsDown size={15}/>Reject</Button></div><Button disabled={!!busy || dirty || editing || approved} onClick={() => action('approve')}>{busy === 'approve' ? <Loader2 className="spin" size={16}/> : <Check size={16}/>} {busy === 'approve' ? 'Validating evidence…' : approved ? 'Approved' : 'Approve draft'}</Button></div>}{confirm && canAct && <Card className="decision-panel"><h3>{confirm === 'reject' ? 'Reject this draft?' : 'Generate a new version?'}</h3><p>{confirm === 'reject' ? 'The draft and evidence will remain in your history.' : 'Existing qualified evidence will be reused. The new draft must be reviewed again.'}</p><label htmlFor="decision-note">{confirm === 'reject' ? 'Reason (optional)' : 'Writing instructions (optional)'}</label><Textarea id="decision-note" maxLength={1000} rows={2} value={confirm === 'reject' ? reason : instructions} onChange={e => confirm === 'reject' ? setReason(e.target.value) : setInstructions(e.target.value)}/><div className="inline-actions"><Button disabled={!!busy} variant={confirm === 'reject' ? 'destructive' : 'default'} onClick={() => action(confirm)}>{busy ? <Loader2 size={15} className="spin"/> : null}{confirm === 'reject' ? 'Confirm rejection' : 'Regenerate draft'}</Button><Button disabled={!!busy} variant="ghost" onClick={() => setConfirm(null)}>Cancel</Button></div></Card>}<Card className="draft-evidence"><div className="section-mini-heading"><h3>Evidence behind the personalisation</h3><span>{supporting.length} referenced claims</span></div>{supporting.length ? renderSupporting() : <p className="quiet-empty">No current claim references. Edited drafts receive new references during approval validation.</p>}</Card></>;
    function renderSupporting() {
        return supporting.map(claim => <div className="draft-claim" key={claim.id}><ShieldCheck size={16}/><div><span className="small-label">{claim.verification === 'supported' ? 'Supported fact' : `${claim.verification} claim`}</span><p>{claim.text}</p>{claim.source_ids.map(id => {
            const source = run.sources.find(s => s.id === id);
            return source ? <a key={id} href={safeUrl(source.url)} target="_blank" rel="noopener noreferrer">{source.title}</a> : null;
        })}</div></div>);
    }
}
