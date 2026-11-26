'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
export function useResource<T>(load: (signal: AbortSignal) => Promise<T>, pollMs = 0) {
    const [data, setData] = useState<T>();
    const [error, setError] = useState<Error>();
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const controller = useRef<AbortController | undefined>(undefined);
    const mounted = useRef(false);
    const loadRef = useRef(load);
    loadRef.current = load;
    // Latest-wins instead of abort-per-call: concurrent refreshes (SSE fires one
    // per event, plus the periodic poll) must never cancel the fetch that carries
    // the terminal state. A monotonic token ensures only the newest *completed*
    // response is applied; superseded in-flight requests resolve and are ignored.
    // The single tracked controller is aborted only on unmount.
    const latest = useRef(0);
    const refresh = useCallback(async () => {
        const token = ++latest.current;
        const current = new AbortController();
        controller.current = current;
        setRefreshing(true);
        try {
            const result = await loadRef.current(current.signal);
            if (mounted.current && token === latest.current) {
                setData(result);
                setError(undefined);
            }
        }
        catch (e) {
            if (mounted.current && token === latest.current && !current.signal.aborted)
                setError(e instanceof Error ? e : new Error('Unable to load data'));
        }
        finally {
            if (mounted.current && token === latest.current) {
                setLoading(false);
                setRefreshing(false);
            }
        }
    }, []);
    useEffect(() => {
        mounted.current = true;
        setLoading(true);
        setData(undefined);
        setError(undefined);
        void refresh();
        return () => {
            mounted.current = false;
            controller.current?.abort();
        };
    }, [load, refresh]);
    useEffect(() => {
        if (!pollMs)
            return;
        const interval = setInterval(() => {
            if (!document.hidden)
                void refresh();
        }, pollMs);
        return () => clearInterval(interval);
    }, [pollMs, refresh]);
    return { data, error, loading, refreshing, refresh };
}
