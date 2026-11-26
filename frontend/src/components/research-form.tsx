'use client';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useState, useRef, type FormEvent } from 'react';
import { ArrowLeft, ArrowRight, Building2, Check, Globe2, Loader2, ScanLine, ShieldCheck, Sparkles, UserRound } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import type { RunInput } from '@/lib/types';
import { Button } from './ui/button';
import { Input, Textarea } from './ui/input';
import { Card } from './ui/card';
import { ErrorNotice } from './feedback';
export function ResearchForm() {
    const router = useRouter();
    const params = useSearchParams();
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<Error>();
    const [fields, setFields] = useState<Record<string, string[]>>({});
    const pending = useRef<{
        fingerprint: string;
        key: string;
    } | undefined>(undefined);
    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (busy)
            return;
        const form = new FormData(event.currentTarget);
        const input: RunInput = { prospect_name: String(form.get('prospect_name')).trim(), designation: String(form.get('designation')).trim(), company_name: String(form.get('company_name')).trim(), company_website: String(form.get('company_website')).trim() || null, product_service: String(form.get('product_service')).trim(), value_proposition: String(form.get('value_proposition')).trim() };
        const fingerprint = JSON.stringify(input);
        if (pending.current?.fingerprint !== fingerprint)
            pending.current = { fingerprint, key: crypto.randomUUID() };
        setBusy(true);
        setError(undefined);
        setFields({});
        try {
            const run = await api.create(input, pending.current!.key);
            router.push(`/runs/${run.run_id}`);
        }
        catch (e) {
            setError(e as Error);
            if (e instanceof ApiError && e.fields)
                setFields(e.fields);
            setBusy(false);
        }
    }
    const fieldError = (name: string) => fields[`body.${name}`]?.join(' ');
    return <div className="page-content form-page"><Link href="/" className="back-link"><ArrowLeft size={15}/>Back to overview</Link><div className="page-heading"><div><div className="eyebrow">START WITH A PERSON. FIND THE SIGNAL.</div><h1>New research<span className="heading-dot">.</span></h1><p>Tell us who you’re reaching out to, and what you bring to the table.</p></div></div><div className="form-layout"><form onSubmit={submit} className="research-form"><Card><div className="form-section-heading"><span className="section-number">01</span><div><h2>The prospect</h2><p>Who would you like to understand better?</p></div><UserRound size={20}/></div><div className="form-fields"><div className="field-row"><Field label="Prospect name" id="prospect_name" error={fieldError('prospect_name')}><Input id="prospect_name" name="prospect_name" placeholder="e.g. Alex Morgan" autoComplete="off" required maxLength={200} defaultValue={params.get('name') || ''}/></Field><Field label="Job title / designation" id="designation" error={fieldError('designation')}><Input id="designation" name="designation" placeholder="e.g. Chief Financial Officer" required maxLength={200}/></Field></div><div className="field-row"><Field label="Company" id="company_name" error={fieldError('company_name')}><Input id="company_name" name="company_name" placeholder="Company name" required maxLength={200}/></Field><Field label="Company website" id="company_website" optional error={fieldError('company_website')}><div className="input-with-icon"><Globe2 size={16}/><Input id="company_website" name="company_website" type="url" placeholder="https://company.com" maxLength={2048}/></div></Field></div></div></Card><Card><div className="form-section-heading"><span className="section-number">02</span><div><h2>Your offer</h2><p>The context that makes a signal relevant.</p></div><Building2 size={20}/></div><div className="form-fields"><Field label="Product or service" id="product_service" error={fieldError('product_service')}><Input id="product_service" name="product_service" placeholder="What are you offering?" required maxLength={500}/></Field><Field label="Value proposition" id="value_proposition" error={fieldError('value_proposition')} hint="Be specific about the problem you solve and who benefits."><Textarea id="value_proposition" name="value_proposition" rows={4} placeholder="We help finance teams…" required maxLength={2000}/></Field></div></Card>{error && <ErrorNotice error={error}/>}<div className="form-submit"><p><ShieldCheck size={16}/>A draft for your review. Never an automatic send.</p><Button disabled={busy} type="submit">{busy ? <><Loader2 size={16} className="spin"/>Starting research…</> : <>Start research<ArrowRight size={17}/></>}</Button></div></form><aside className="research-guide"><div className="guide-label"><Sparkles size={16}/>WHAT HAPPENS NEXT</div><h3>Research with a reason.</h3><p>We look for a business event that matters to this person and your offer.</p><div className="guide-steps">{[{ icon: Globe2, title: 'Discover the context', text: 'Search real public sources for company and prospect information.' }, { icon: ScanLine, title: 'Find the strongest signal', text: 'Evaluate credibility, recency and relevance to their role.' }, { icon: UserRound, title: 'Put you in control', text: 'Review the evidence, edit the email and decide what comes next.' }].map((step, i) => <div key={step.title}><span><step.icon size={17}/></span><div><small>STEP 0{i + 1}</small><strong>{step.title}</strong><p>{step.text}</p></div></div>)}</div><div className="guide-abstain"><Check size={17}/><p>No strong signal? We’ll tell you.<br />We don’t fill the gaps with fiction.</p></div></aside></div></div>;
}
function Field({ id, label, optional, error, hint, children }: {
    id: string;
    label: string;
    optional?: boolean;
    error?: string;
    hint?: string;
    children: React.ReactNode;
}) {
    return <div className="field"><label htmlFor={id}>{label}{optional ? <span>Optional</span> : <span className="required-dot">*</span>}</label>{children}{error && <small className="field-error" role="alert">{error}</small>}{hint && <small className="field-hint">{hint}</small>}</div>;
}
