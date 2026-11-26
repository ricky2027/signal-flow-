'use client';
import Link from 'next/link';
import { ArrowUpRight, ChevronDown, Search, Users } from 'lucide-react';
import { useState } from 'react';
import type { RunSummary, Status } from '@/lib/types';
import { statuses } from '@/lib/status';
import { dateTime, initials } from '@/lib/utils';
import { StatusBadge } from './status-badge';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { EmptyState } from './feedback';
export function RunTable({ runs, hasMore, loadMore, loading, reviewOnly = false }: {
    runs: RunSummary[];
    hasMore?: boolean;
    loadMore?: () => void;
    loading?: boolean;
    reviewOnly?: boolean;
}) {
    const [search, setSearch] = useState('');
    const [status, setStatus] = useState('all');
    const filtered = runs.filter(r => (!reviewOnly || r.status === 'awaiting_review') && (status === 'all' || r.status === status) && `${r.prospect_name} ${r.company_name}`.toLowerCase().includes(search.toLowerCase()));
    return <div className="card history-card"><div className="table-toolbar"><div className="search-input"><Search size={16}/><Input aria-label="Search loaded runs" placeholder="Search prospects or companies…" value={search} onChange={e => setSearch(e.target.value)}/></div><div className="select-wrap"><select aria-label="Filter status" value={status} onChange={e => setStatus(e.target.value)}><option value="all">All statuses</option>{Object.entries(statuses).map(([value, info]) => <option key={value} value={value}>{info.label}</option>)}</select><ChevronDown size={14}/></div></div>{filtered.length ? <div className="table-scroll"><table><thead><tr><th>PROSPECT</th><th>COMPANY</th><th>STATUS</th><th>CREATED</th><th><span className="sr-only">Open</span></th></tr></thead><tbody>{filtered.map(run => <tr key={run.id}><td><Link href={`/runs/${run.id}`} className="prospect-cell"><span className="person-avatar">{initials(run.prospect_name)}</span><span><strong>{run.prospect_name}</strong><small>Run {run.id.slice(0, 8)}</small></span></Link></td><td>{run.company_name}</td><td><StatusBadge status={run.status as Status}/></td><td className="date-cell">{dateTime(run.created_at)}</td><td><Link className="table-open" href={`/runs/${run.id}`} aria-label={`Open research for ${run.prospect_name}`}><ArrowUpRight size={17}/></Link></td></tr>)}</tbody></table></div> : <EmptyState icon={<Users size={25}/>} title={search || status !== 'all' ? 'No matching runs' : reviewOnly ? 'Your review queue is clear' : 'Your first signal starts here'} description={search || status !== 'all' ? 'Try a different search or status. Filters apply to the runs loaded below.' : reviewOnly ? 'Drafts that pass evidence validation will appear here for your review.' : 'Add a prospect and an offer. We’ll research the context and surface what matters.'} action={!search && status === 'all' && !reviewOnly ? <Button asChild size="sm"><Link href="/research/new">Start new research<ArrowUpRight size={15}/></Link></Button> : undefined}/>}<div className="table-bottom"><span>{filtered.length} of {runs.length} loaded runs{hasMore ? ' · More available' : ''}</span>{hasMore && <Button variant="outline" size="sm" disabled={loading} onClick={loadMore}>{loading ? 'Loading…' : 'Load more runs'}</Button>}<span>All times in your local timezone</span></div></div>;
}
