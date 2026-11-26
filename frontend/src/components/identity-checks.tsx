import type { RunDetail } from '@/lib/types';
import { Card } from './ui/card';
import { safeUrl } from '@/lib/utils';
export function IdentityChecksPanel({ run }: { run: RunDetail }) {
    const checks = run.identity_checks;
    if (!checks) return null;
    const rows = [
        ['prospect_identity', 'Prospect identity'],
        ['company_association', 'Company association'],
        ['title_match', 'Title match'],
        ['role_currentness', 'Current role · dated evidence'],
    ] as const;
    return <Card className="source-card"><h3>Independent identity checks</h3>
        {rows.map(([key, label]) => <div className="claim-row" key={key}><div>
            <span className="small-label">{label}</span><p>{checks[key].status.replaceAll('_', ' ')}</p>
            {checks[key].reasons.map(reason => <small key={reason}>{reason.replaceAll('_', ' ')}</small>)}
            {checks[key].source_ids.map(id => {
                const source = run.sources.find(s => s.id === id);
                return source ? <p key={id}><a href={safeUrl(source.url)} target="_blank" rel="noopener noreferrer">{source.title}</a></p> : null;
            })}
        </div></div>)}
        {checks.prospect_identity.status === 'verified' && checks.company_association.status === 'verified' && checks.role_currentness.status !== 'verified' &&
            <p>Identity and company association are corroborated. Current employment is unverified. Evaluation can use verified company events; unverified roles and duties are excluded from scoring and outreach.</p>}
    </Card>;
}
