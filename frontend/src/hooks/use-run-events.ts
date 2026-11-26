'use client';
import { useEffect, useRef, useState, useCallback } from 'react';
import type { RunEvent, RunDetail } from '@/lib/types';
import { active } from '@/lib/status';
import { api } from '@/lib/api';
const eventNames = ['run.queued', 'stage.started', 'research.updated', 'stage.completed', 'stage.result', 'draft.created', 'run.status_changed', 'run.failed'];
export function useRunEvents(id: string, run: RunDetail | undefined, refresh: () => Promise<void>) {
    const [events, setEvents] = useState<RunEvent[]>([]);
    const [connection, setConnection] = useState('connecting');
    const [notices, setNotices] = useState<Array<{
        at: string;
        text: string;
    }>>([]);
    const [epoch, setEpoch] = useState(0);
    const current = useRef(run);
    current.current = run;
    const refreshRef = useRef(refresh);
    refreshRef.current = refresh;
    const cursor = useRef(0);
    const closed = useRef(false);
    const reconnect = useCallback(() => setEpoch(x => x + 1), []);
    useEffect(() => {
        setEvents([]);
        setNotices([]);
        cursor.current = 0;
    }, [id]);
    useEffect(() => {
        let disposed = false;
        closed.current = false;
        const source = new EventSource(`/api/v1/runs/${encodeURIComponent(id)}/events?after=${cursor.current}`);
        source.onopen = () => {
            if (!disposed)
                setConnection('connected');
        };
        const receive = (message: MessageEvent) => {
            try {
                const event = JSON.parse(message.data) as RunEvent;
                if (event.run_id !== id || typeof event.sequence !== 'number')
                    return;
                cursor.current = Math.max(cursor.current, event.sequence);
                setEvents(items => items.some(e => e.sequence === event.sequence) ? items : [...items, event].sort((a, b) => a.sequence - b.sequence));
                void refreshRef.current();
            }
            catch {
                setNotices(items => [...items.slice(-9), { at: new Date().toISOString(), text: 'An unreadable live event was skipped. Refreshing the persisted run.' }]);
                void refreshRef.current();
            }
        };
        eventNames.forEach(name => source.addEventListener(name, receive as EventListener));
        source.onerror = () => {
            if (disposed)
                return;
            // The server intentionally ends terminal streams. Confirm actual persisted status
            // before treating an EOF as a completed history sync.
            void api.detail(id).then(detail => {
                if (disposed)
                    return;
                void refreshRef.current();
                if (!active(detail.status)) {
                    source.close();
                    closed.current = true;
                    setConnection('synced');
                }
                else {
                    setConnection('reconnecting');
                    setNotices(items => [...items.slice(-9), { at: new Date().toISOString(), text: 'Live connection interrupted. Reconnecting from the last received event; research continues on the backend.' }]);
                }
            }).catch(() => {
                if (!disposed) {
                    setConnection('reconnecting');
                    setNotices(items => [...items.slice(-9), { at: new Date().toISOString(), text: 'Cannot reach live updates. Retrying the connection; the last saved results remain visible.' }]);
                }
            });
        };
        setConnection('connecting');
        return () => {
            disposed = true;
            source.close();
        };
    }, [id, epoch]);
    useEffect(() => {
        if (run && active(run.status) && closed.current) {
            closed.current = false;
            setEpoch(x => x + 1);
        }
    }, [run?.status]);
    return { events, connection, notices, reconnect };
}
