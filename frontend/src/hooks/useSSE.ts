"use client";

import { useEffect, useRef, useState } from "react";

export interface SSEOptions<T> {
  url: string;
  onMessage: (data: T) => void;
  enabled?: boolean;
}

export function useSSE<T>({ url, onMessage, enabled = true }: SSEOptions<T>) {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!enabled) return;

    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setConnected(true);
      setError(null);
    };

    es.onmessage = (evt) => {
      try {
        const parsed = JSON.parse(evt.data) as T;
        onMessageRef.current(parsed);
      } catch {
        /* ignore malformed chunks */
      }
    };

    es.onerror = () => {
      setConnected(false);
      setError("SSE connection lost — retrying…");
      es.close();
    };

    return () => {
      es.close();
      setConnected(false);
    };
  }, [url, enabled]);

  return { connected, error };
}
