import { RunDetailScreen } from '@/components/run-detail';
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
    const { id } = await params;
    return <RunDetailScreen id={id}/>;
}
