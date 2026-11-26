import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
export function cn(...values: ClassValue[]) {
    return twMerge(clsx(values));
}
export function dateTime(value: string | null) {
    if (!value)
        return 'Not recorded';
    return new Date(value).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
export function dateOnly(value: string | null) {
    return value ? new Date(value.length === 10 ? `${value}T12:00:00` : value).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : 'Date unknown';
}
export function initials(name: string) {
    return name.split(/\s+/).slice(0, 2).map(x => x[0] || '').join('').toUpperCase();
}
export function safeUrl(url: string) {
    try {
        const u = new URL(url);
        return ['https:', 'http:'].includes(u.protocol) ? u.href : undefined;
    }
    catch {
        return undefined;
    }
}
// Display matching only; retrieval authorization remains in the backend.
export function evidenceUrlKey(value: string) {
    const safe = safeUrl(value);
    if (!safe) return undefined;
    const url = new URL(safe);
    url.hash = '';
    const tracking = new Set(['gclid', 'fbclid', 'dclid', 'msclkid', 'msockid', 'mc_cid', 'mc_eid', '_ga']);
    for (const key of Array.from(url.searchParams.keys())) {
        if (key.toLowerCase().startsWith('utm_') || tracking.has(key.toLowerCase())) url.searchParams.delete(key);
    }
    return url.href;
}
