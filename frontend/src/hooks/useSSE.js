import { useEffect, useRef, useState } from "react";

/**
 * Subscribes to a job's SSE stream and keeps the latest status snapshot in
 * state. The backend sends a full JobStatus payload on every change (not a
 * diff), so this just replaces state on each message - simplest thing that
 * can't drift out of sync.
 */
export function useSSE(url, { enabled }) {
  const [status, setStatus] = useState(null);
  const [connectionError, setConnectionError] = useState(null);
  const sourceRef = useRef(null);

  useEffect(() => {
    if (!enabled || !url) return undefined;

    const source = new EventSource(url);
    sourceRef.current = source;

    source.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        setStatus(parsed);
        if (parsed.state === "complete" || parsed.state === "error") {
          source.close();
        }
      } catch (err) {
        console.error("Failed to parse SSE payload", err);
      }
    };

    source.onerror = () => {
      setConnectionError("Lost connection to the job stream.");
      source.close();
    };

    return () => source.close();
  }, [url, enabled]);

  return { status, connectionError };
}
