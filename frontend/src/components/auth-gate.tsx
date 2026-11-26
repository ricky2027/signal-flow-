'use client';
import { useCallback, useState, type FormEvent, type ReactNode } from 'react';
import { api, ApiError } from '@/lib/api';
import { useResource } from '@/hooks/use-resource';
import { ArrowRight, KeyRound, LockKeyhole, ShieldCheck, Loader2 } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { ErrorNotice, Loading } from './feedback';
export function AuthGate({ children }: {
    children: ReactNode;
}) {
    const load = useCallback((signal: AbortSignal) => api.history('?limit=1', signal), []);
    const auth = useResource(load);
    const [code, setCode] = useState('');
    const [error, setError] = useState<Error>();
    const [busy, setBusy] = useState(false);
    async function login(e: FormEvent) {
        e.preventDefault();
        setBusy(true);
        setError(undefined);
        try {
            await api.login(code);
            setCode('');
            await auth.refresh();
        }
        catch (e) {
            setError(e as Error);
        }
        finally {
            setBusy(false);
        }
    }
    if (auth.loading)
        return <Loading />;
    if (auth.error && !(auth.error instanceof ApiError && auth.error.status === 401))
        return <div className="page-content"><ErrorNotice error={auth.error} retry={auth.refresh}/></div>;
    if (auth.error)
        return <div className="auth-wrap"><div className="auth-card"><div className="eyebrow"><span className="mini-mark"/>YOUR GTM WORKSPACE</div><div className="auth-symbol"><KeyRound size={28}/></div><h1>Good outreach<br />starts with a signal.</h1><p>Research with context. Write with evidence.<br />Keep a human in control.</p><form onSubmit={login}><label htmlFor="access-code">Workspace access code</label><Input id="access-code" type="password" autoComplete="current-password" required maxLength={200} value={code} onChange={e => setCode(e.target.value)} placeholder="Enter your access code"/>{error && <ErrorNotice error={error}/>}<Button type="submit" disabled={busy || !code.trim()}>{busy ? <Loader2 size={17} className="spin"/> : <>Open workspace<ArrowRight size={17}/></>}</Button></form><div className="auth-foot"><LockKeyhole size={13}/>Your research history is private to this browser session.</div></div><div className="auth-aside"><div className="orbital"><RadioArt /></div><span className="eyebrow">FROM PROSPECT TO PERSONAL</span><h2>Less searching.<br />More substance.</h2><p>Find the business event.<br />Understand why it matters.<br />Start a better conversation.</p><span className="safety-line"><ShieldCheck size={16}/>Every draft waits for your review.</span></div></div>;
    return <>{children}</>;
}
function RadioArt() {
    return <svg viewBox="0 0 180 180" fill="none" aria-hidden="true"><circle cx="90" cy="90" r="76" stroke="currentColor" strokeOpacity=".14"/><circle cx="90" cy="90" r="53" stroke="currentColor" strokeOpacity=".22"/><circle cx="90" cy="90" r="29" stroke="currentColor" strokeOpacity=".4"/><path d="M28 90h35l9-18 13 38 13-49 13 29h41" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/><circle cx="90" cy="14" r="4" fill="currentColor"/></svg>;
}
