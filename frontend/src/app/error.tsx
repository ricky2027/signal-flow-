'use client';
import { useEffect } from 'react';
import { ErrorNotice } from '@/components/feedback';
export default function ErrorPage({ reset }: {
    error: Error;
    reset: () => void;
}) {
    return <div className="page-content"><h1>Something interrupted this view.</h1><ErrorNotice error={new Error('Your persisted research is safe. Reload this view to try again.')} retry={reset}/></div>;
}
