import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

const API_BASE = "/api/v1";

async function apiFetch(path: string, options?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) throw new Error(`API Error: ${res.statusText}`);
  const data = await res.json();
  if (data && typeof data === 'object' && 'success' in data && 'data' in data) {
    return data.data;
  }
  return data;
}

// Agents
export const useListAgents = (options?: { query?: any }) => 
  useQuery<any[]>({ queryKey: ["/api/agents"], queryFn: () => apiFetch("/agents"), ...options?.query });

export const useGetAgent = (id: number, options?: { query?: any }) => 
  useQuery<any>({ queryKey: ["/api/agents", id], queryFn: () => apiFetch(`/agents/${id}`), ...options?.query });

export const useCreateAgent = (options?: { mutation?: any }) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ data }: { data: any }) => apiFetch("/agents", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["/api/agents"] });
      options?.mutation?.onSuccess?.();
    },
    ...options?.mutation
  });
};

export const useUpdateAgent = (options?: { mutation?: any }) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number, data: any }) => apiFetch(`/agents/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }),
    onSuccess: (_data: any, vars: any) => {
      qc.invalidateQueries({ queryKey: ["/api/agents", vars.id] });
      options?.mutation?.onSuccess?.();
    },
    ...options?.mutation
  });
};

export const useDeleteAgent = (options?: { mutation?: any }) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id }: { id: number }) => apiFetch(`/agents/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["/api/agents"] });
      options?.mutation?.onSuccess?.();
    },
    ...options?.mutation
  });
};

// Conversations
export const useListConversations = (params?: any, options?: { query?: any }) => useQuery<any[]>({ 
  queryKey: ["/api/conversations", params], 
  queryFn: () => {
    const search = params ? `?${new URLSearchParams(params).toString()}` : "";
    return apiFetch(`/conversations${search}`);
  },
  ...options?.query
});

export const useCreateConversation = (options?: { mutation?: any }) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ data }: { data: any }) => apiFetch("/conversations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }),
    onSuccess: (data: any) => {
      qc.invalidateQueries({ queryKey: ["/api/conversations"] });
      options?.mutation?.onSuccess?.(data);
    },
    ...options?.mutation
  });
};

export const useListMessages = (id: number, options?: { query?: any }) => useQuery<any[]>({ 
  queryKey: [`/api/conversations/${id}/messages`], 
  queryFn: () => apiFetch(`/conversations/${id}/messages`),
  ...options?.query
});

export interface ServerSentEvent {
    id?: string;
    type: "token" | "message" | "error" | "final" | "plan" | "agent" | "builder_ui";
    content?: string;
    step?: number;
    agent?: "planner" | "memory" | "tool" | "executor" | "orchestrator" | "builder";
    role?: "system" | "user" | "assistant" | "planner" | "memory" | "executor" | "orchestrator";
    status?: "running" | "done" | "error" | "skipped";
    provider?: string;
    model?: string;
}

export type TokenCallback = (token: string) => void;
export type EventCallback = (event: ServerSentEvent) => void;
export type BuilderUICallback = (content: string) => void;

export interface StreamOptions {
    onMessage?: TokenCallback;
    onToken?: TokenCallback;
    onEvent?: EventCallback;
    onBuilderUI?: (content: string) => void;
    onError?: (err: any) => void;
    onClose?: () => void;
}

export function streamChat(
    convoId: number,
    taskId: string,
    query: string,
    options: StreamOptions,
    provider: string = "auto",
    model: string = "",
    lastEventId?: string
) {
    const url = new URL(`${window.location.origin}${API_BASE}/chat/stream`);
    url.searchParams.append("convoId", convoId.toString());
    url.searchParams.append("taskId", taskId);
    url.searchParams.append("query", query);
    url.searchParams.append("provider", provider);
    if (model) url.searchParams.append("model", model);
    if (lastEventId) url.searchParams.append("lastEventId", lastEventId);

    const es = new EventSource(url.toString());

    es.onmessage = (e) => {
        try {
            const event: ServerSentEvent = JSON.parse(e.data);
            if (event.type === "token" && options.onToken) {
                options.onToken(event.content || "");
            } else if (event.type === "builder_ui" && options.onBuilderUI) {
                options.onBuilderUI(event.content || "");
            } else if (options.onEvent) {
                options.onEvent(event);
            }
            if (event.type === "final" || event.type === "error") {
                es.close();
                if (options.onClose) options.onClose();
            }
        } catch (err) {
            console.error("Failed to parse SSE event", err);
        }
    };

    es.onerror = (err) => {
        es.close();
        if (options.onError) options.onError(err);
        if (options.onClose) options.onClose();
    };

    return () => {
        es.close();
        if (options.onClose) options.onClose();
    };
}

export const useSendMessage = (options?: { mutation?: any }) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number, data: { content: string, mode?: string } }) => 
      apiFetch(`/conversations/${id}/messages`, { 
        method: "POST", 
        headers: { "Content-Type": "application/json" }, 
        body: JSON.stringify(data) 
      }),
    onSuccess: (_data: any, vars: any) => {
      qc.invalidateQueries({ queryKey: [`/api/conversations/${vars.id}/messages`] });
      options?.mutation?.onSuccess?.();
    },
    ...options?.mutation
  });
};

// Tasks
export const useListTasks = (params?: any, options?: { query?: any }) => useQuery<any[]>({ 
  queryKey: ["/api/tasks", params], 
  queryFn: () => {
    const search = params ? `?${new URLSearchParams(params).toString()}` : "";
    return apiFetch(`/tasks${search}`);
  },
  ...options?.query
});

export const useCreateTask = (options?: { mutation?: any }) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ data }: { data: any }) => apiFetch("/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["/api/tasks"] });
      options?.mutation?.onSuccess?.();
    },
    ...options?.mutation
  });
};

export const useUpdateTask = (options?: { mutation?: any }) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number, data: any }) => apiFetch(`/tasks/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["/api/tasks"] });
      options?.mutation?.onSuccess?.();
    },
    ...options?.mutation
  });
};


// Stats
export const useGetStats = () => useQuery({ queryKey: ["/api/stats"], queryFn: () => apiFetch("/stats") });

// Models
export const useListModels = () => useQuery<any>({ queryKey: ["/api/models"], queryFn: () => apiFetch("/models") });

// Settings & Connectors
export const useUpdateSettings = () => useMutation({
  mutationFn: (data: any) => apiFetch("/settings/keys", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) })
});

/** Fetch current key configuration status from backend (masked values) */
export const useGetSettingsKeys = (options?: { query?: any }) =>
  useQuery<Record<string, { name: string; configured: boolean; preview: string }>>({
    queryKey: ["/api/settings/keys"],
    queryFn: () => apiFetch("/settings/keys"),
    staleTime: 30_000,
    ...options?.query,
  });

export const useConnectProvider = () => useMutation({
  mutationFn: ({ provider, data }: { provider: string, data: any }) => 
    apiFetch(`/connect/${provider}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) })
});

// ─── Builder Engine ───────────────────────────────────────────────────────────

export interface BuilderPreferences {
    design: "modern" | "luxury" | "colorful" | "simple";
    type: "ecommerce" | "dashboard" | "blog" | "portfolio" | "landing";
    backend: boolean;
    features: { auth: boolean; payment: boolean; dashboard: boolean; };
}

export interface BuilderCheckResult {
    has_preferences: boolean;
    preferences: Partial<BuilderPreferences>;
}

export interface BuildResult {
    status: string;
    session_id: string;
    files_generated: string[];
    output_path: string;
}

/** Check if the local_user has saved builder preferences in PCO. */
export const useBuilderCheck = (options?: { query?: any }) =>
    useQuery<BuilderCheckResult>({
        queryKey: ["/api/v1/builder/check"],
        queryFn: () => apiFetch("/builder/check"),
        staleTime: 5_000,
        ...options?.query,
    });

/** Save builder preferences. Usually called when user clicks the quick-pick buttons. */
export const useSaveBuilderPrefs = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (prefs: Partial<BuilderPreferences>) =>
            apiFetch("/builder/preferences", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(prefs),
            }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["/api/v1/builder/check"] });
        },
    });
};

/** Trigger a synchronous build (non-streaming). Returns session_id + file list. */
export const useDirectBuild = () =>
    useMutation({
        mutationFn: (prefs: Partial<BuilderPreferences>) =>
            apiFetch("/builder/build", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(prefs),
            }) as Promise<BuildResult>,
    });

/** Get the preview URL for a completed build session. */
export function getBuilderPreviewUrl(sessionId: string): string {
    return `${API_BASE}/builder/preview/${encodeURIComponent(sessionId)}`;
}
