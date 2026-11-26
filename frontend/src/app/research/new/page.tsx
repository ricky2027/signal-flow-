import { Suspense } from 'react';
import { ResearchForm } from '@/components/research-form';
import { Loading } from '@/components/feedback';
export default function Page() {
    return <Suspense fallback={<Loading />}><ResearchForm /></Suspense>;
}
