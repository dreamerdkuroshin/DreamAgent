import { useState, useCallback, useRef, useEffect } from "react";

export function useStreaming() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastEventIdRef = useRef<string | null>(null);

  const startStream = useCallback(
    (url: string, onData: (data: any) => void, onComplete: () => void) => {
      setIsStreaming(true);
      setErrorMsg(null);

      const connect = () => {
        // Append lastEventId if resuming
        const connectUrl = lastEventIdRef.current 
            ? `${url}${url.includes('?') ? '&' : '?'}lastEventId=${lastEventIdRef.current}` 
            : url;

        const es = new EventSource(connectUrl);
        eventSourceRef.current = es;

        es.onmessage = (event) => {
          try {
            if (event.lastEventId) {
               lastEventIdRef.current = event.lastEventId;
            }
            
            const data = JSON.parse(event.data);
            onData(data);
            
            if (data.type === "final") {
              es.close();
              setIsStreaming(false);
              lastEventIdRef.current = null;
              onComplete();
            } else if (data.type === "error") {
              es.close();
              setIsStreaming(false);
              lastEventIdRef.current = null;
              setErrorMsg(data.content || "An error occurred during execution.");
              onComplete();
            }
          } catch (err) {
            console.error("Failed to parse SSE JSON", err);
          }
        };

        es.onerror = () => {
          es.close();
          // Recover gracefuly: reconnect logic using lastEventId
          retryTimeoutRef.current = setTimeout(() => connect(), 2000);
        };
      };

      connect();
    },
    []
  );

  const cancelStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
    }
    setIsStreaming(false);
    lastEventIdRef.current = null;
    setErrorMsg("Stream willfully cancelled.");
  }, []);

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) eventSourceRef.current.close();
      if (retryTimeoutRef.current) clearTimeout(retryTimeoutRef.current);
    };
  }, []);

  return { isStreaming, errorMsg, setErrorMsg, startStream, cancelStream };
}
