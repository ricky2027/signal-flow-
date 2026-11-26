import type { Status } from '@/lib/types';
import { statuses } from '@/lib/status';
export function StatusBadge({ status }: {
    status: Status;
}) {
    const info = statuses[status] || { label: status, tone: 'neutral' };
    return <span className={`status-badge ${info.tone}`}><span className={status === 'running' ? 'status-dot pulse' : 'status-dot'}/>{info.label}</span>;
}
