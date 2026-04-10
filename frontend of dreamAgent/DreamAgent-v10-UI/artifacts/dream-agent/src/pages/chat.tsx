import { useState, useRef, useEffect } from "react";
import { useLocation } from "wouter";
import {
  useListAgents,
  useListConversations,
  useListMessages,
  useCreateConversation
} from "@workspace/api-client-react";
import { MessageSquare, Plus, Loader2, Cpu, ChevronRight, Activity, Pin, Trash, MonitorPlay } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Layout } from "@/components/layout";
import { Button, Input, Modal, Card } from "@/components/ui-elements";
import { cn } from "@/lib/utils";
import { useForm } from "react-hook-form";
import { useAppStore } from "@/store/app.store";
import { ChatContainer } from "@/features/chat/components/ChatContainer";
import { LiveExecutionPanel } from "@/features/chat/components/LiveExecutionPanel";
import { useChat } from "@/features/chat/hooks/useChat";
import { AgentTracePanel } from "@/components/chat/AgentTracePanel";
import { BuilderPanel } from "@/features/chat/components/BuilderPanel";

export default function Chat() {
  const [location] = useLocation();
  const searchParams = new URLSearchParams(window.location.search);
  const initialAgentId = searchParams.get("agentId") || undefined;

  const { mode: activeMode } = useAppStore();
  const [activeConvoId, setActiveConvoId] = useState<number | null>(null);
  const [isNewConvoOpen, setIsNewConvoOpen] = useState(false);
  const [traceOpen, setTraceOpen] = useState(false);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [availableProviders, setAvailableProviders] = useState<any[]>([]);
  const [selectedProvider, setSelectedProvider] = useState("auto");
  const [selectedModel, setSelectedModel] = useState("");

  // Builder Panel State (Moved up from ActiveChatSession)
  const [builderSessionId, setBuilderSessionId] = useState<string | null>(null);

  // Check URL for sessionId on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sid = params.get("sessionId");
    if (sid) {
      setBuilderSessionId(sid);
      // Clean up URL
      const newUrl = window.location.pathname;
      window.history.replaceState({}, '', newUrl);
    }
  }, []);

  const { data: conversations, isLoading: convosLoading } = useListConversations();
  const { data: messages, isLoading: messagesLoading } = useListMessages(activeConvoId!, { query: { enabled: !!activeConvoId } });

  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; convoId: number } | null>(null);
  const [pinnedConvos, setPinnedConvos] = useState<number[]>(() => {
    try { return JSON.parse(localStorage.getItem("pinned_convos") || "[]"); } catch { return []; }
  });

  const togglePin = (id: number) => {
    setPinnedConvos(prev => {
      const updated = prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id];
      localStorage.setItem("pinned_convos", JSON.stringify(updated));
      return updated;
    });
    setContextMenu(null);
  };

  const queryClient = useQueryClient();
  const deleteConvo = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/v1/conversations/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error("Deletion failed");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/v1/conversations"] });
      setContextMenu(null);
      if (activeConvoId && contextMenu?.convoId === activeConvoId) setActiveConvoId(null);
    }
  });

  const sortedConversations = conversations ? [...conversations].sort((a: any, b: any) => {
    const aPinned = pinnedConvos.includes(a.id);
    const bPinned = pinnedConvos.includes(b.id);
    if (aPinned && !bPinned) return -1;
    if (!aPinned && bPinned) return 1;
    return 0;
  }) : [];

  // Fix #19: Populate provider dropdown from backend on mount
  useEffect(() => {
    fetch("/api/v1/models")
      .then(r => r.json())
      .then(data => {
        const providers = Array.isArray(data) ? data : (data?.providers ?? data?.data ?? []);
        setAvailableProviders(providers);
      })
      .catch(() => setAvailableProviders([]));
  }, []);

  const activeTitle = conversations?.find((c: any) => c.id === activeConvoId)?.title || "Unified Comms Channel";


  return (
    <Layout>
      <div className="h-[calc(100vh-6rem)] md:h-[calc(100vh-4.5rem)] flex gap-4 overflow-hidden pt-2 p-4 md:p-0">

        {/* Sidebar - Convo List (Redesigned for OS feel) */}
        <aside className="w-72 flex-shrink-0 hidden lg:flex flex-col bg-black/40 backdrop-blur-md rounded-2xl border border-white/5 overflow-hidden">
          <div className="p-5 border-b border-white/5 flex justify-between items-center bg-white/5">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-primary animate-pulse shadow-[0_0_8px_rgba(0,240,255,0.8)]" />
              <h2 className="text-xs font-bold text-foreground uppercase tracking-[0.2em]">Channels</h2>
            </div>
            <button
              onClick={() => setIsNewConvoOpen(true)}
              className="p-1.5 rounded-lg bg-primary/10 border border-primary/20 text-primary hover:bg-primary hover:text-black transition-all"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
            {convosLoading ? (
              <div className="flex flex-col items-center justify-center h-32 gap-3 opacity-40">
                <Loader2 className="w-5 h-5 animate-spin" />
                <span className="text-[10px] font-mono uppercase tracking-widest">Scanning Nodes...</span>
              </div>
            ) : sortedConversations.map((convo: any) => (
              <button
                key={convo.id}
                onClick={() => { setActiveConvoId(convo.id); setContextMenu(null); }}
                onContextMenu={(e) => {
                  e.preventDefault();
                  setContextMenu({ x: e.pageX, y: e.pageY, convoId: convo.id });
                }}
                className={cn(
                  "w-full text-left p-4 rounded-xl transition-all duration-300 group relative overflow-hidden flex items-center justify-between",
                  activeConvoId === convo.id
                    ? "bg-primary/10 border border-primary/20 shadow-lg"
                    : "hover:bg-white/5 border border-transparent"
                )}
              >
                <div className="z-10 min-w-0">
                  <div className="flex items-center gap-1.5">
                    {pinnedConvos.includes(convo.id) && <Pin className="w-3 h-3 flex-shrink-0 text-cyan-400 rotate-45" />}
                    <div className={cn(
                      "font-bold text-xs truncate transition-colors",
                      activeConvoId === convo.id ? "text-primary" : "text-foreground/70 group-hover:text-foreground"
                    )}>{convo.title}</div>
                  </div>
                  <div className="text-[10px] text-muted-foreground/60 truncate mt-1 flex items-center gap-1 font-mono uppercase">
                    <Cpu className="w-3 h-3 opacity-50" /> {convo.agentName || "Agent-01"}
                  </div>
                </div>
                {activeConvoId === convo.id && <ChevronRight className="w-4 h-4 text-primary animate-in slide-in-from-left-2" />}
                {activeConvoId === convo.id && <div className="absolute inset-0 bg-gradient-to-r from-primary/5 to-transparent pointer-events-none" />}
              </button>
            ))}
          </div>
        </aside>
        
        {activeConvoId ? (
          <ActiveChatSession
            key={activeConvoId || "builder-only"}
            activeConvoId={activeConvoId}
            activeTitle={activeTitle}
            messages={messages || []}
            messagesLoading={messagesLoading}
            availableProviders={availableProviders}
            selectedProvider={selectedProvider}
            selectedModel={selectedModel}
            setSelectedProvider={setSelectedProvider}
            setSelectedModel={setSelectedModel}
            builderSessionId={builderSessionId}
            setBuilderSessionId={setBuilderSessionId}
          />
        ) : builderSessionId ? (
          <div className="flex-1 flex gap-4 min-w-0 transition-all duration-500 ease-in-out pr-0">
             <div className="h-full flex-1 animate-in slide-in-from-right-8 duration-500 ease-out">
              <div className="h-full rounded-2xl overflow-hidden shadow-2xl shadow-black/50">
                <BuilderPanel
                  sessionId={builderSessionId!}
                  onClose={() => setBuilderSessionId(null)}
                  isFocusMode={true}
                  setFocusMode={() => {}}
                />
              </div>
            </div>
          </div>
        ) : (
          <main className="flex-1 flex gap-4 min-w-0 transition-all duration-500 ease-in-out">
            <div className="flex-1 min-w-0 h-full flex flex-col">
              <div className="flex-1 min-w-0">
                <div className="h-full flex flex-col items-center justify-center text-muted-foreground bg-black/20 border border-white/5 rounded-2xl backdrop-blur-md">
                  <div className="w-20 h-20 rounded-full bg-primary/5 border border-primary/10 flex items-center justify-center mb-6 neon-glow">
                    <MessageSquare className="w-10 h-10 text-primary/40" />
                  </div>
                  <h3 className="text-lg font-bold text-foreground mb-2 uppercase tracking-widest">Command Interface Offline</h3>
                  <p className="text-sm opacity-60 mb-8 max-w-xs text-center">Select an encrypted channel from the sidebar or initialize a new neural link.</p>
                  <Button onClick={() => setIsNewConvoOpen(true)} size="lg" className="px-8 border border-primary/30">
                    Initialize Link
                  </Button>
                </div>
              </div>
            </div>
          </main>
        )}

      </div>

      <NewConversationModal isOpen={isNewConvoOpen} onClose={() => setIsNewConvoOpen(false)} onSelect={setActiveConvoId} />

      {contextMenu && (
        <>
          <div className="fixed inset-0 z-50" onClick={() => setContextMenu(null)} onContextMenu={(e) => { e.preventDefault(); setContextMenu(null); }} />
          <div
            className="fixed z-[60] py-1 bg-black/90 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl flex flex-col min-w-[160px] overflow-hidden"
            style={{ top: contextMenu.y, left: contextMenu.x }}
          >
            <button
              className="flex items-center gap-2 px-4 py-2 text-sm text-white/80 hover:bg-white/10 hover:text-white transition-colors text-left"
              onClick={() => togglePin(contextMenu.convoId)}
            >
              <Pin className="w-4 h-4" /> {pinnedConvos.includes(contextMenu.convoId) ? "Unpin Channel" : "Pin Channel"}
            </button>
            <button
              className="flex items-center gap-2 px-4 py-2 text-sm text-red-400 hover:bg-red-500/20 hover:text-red-300 transition-colors text-left"
              onClick={() => deleteConvo.mutate(contextMenu.convoId)}
            >
              {deleteConvo.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash className="w-4 h-4" />} Delete Channel
            </button>
          </div>
        </>
      )}
    </Layout>
  );
}

function ActiveChatSession({
  activeConvoId,
  activeTitle,
  messages,
  messagesLoading,
  availableProviders,
  selectedProvider,
  selectedModel,
  setSelectedProvider,
  setSelectedModel,
  builderSessionId,
  setBuilderSessionId
}: any) {
  const { mode: activeMode } = useAppStore();
  const [msgInput, setMsgInput] = useState("");
  const [traceOpen, setTraceOpen] = useState(false);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [optimisticUserMsg, setOptimisticUserMsg] = useState<any | null>(null);

  // Focus Mode State
  const [isFocusMode, setIsFocusMode] = useState(false);
  const [resumeData, setResumeData] = useState<any>(null);
  const [dismissResume, setDismissResume] = useState(false);

  const { liveMessage, isStreaming, errorMsg, sendMessage, cancelStream, taskId } = useChat(activeConvoId, setMsgInput);

  // Resume UX check
  useEffect(() => {
    fetch("/api/v1/builder/check")
      .then(r => r.json())
      .then(d => {
        if (d.last_build && d.last_build.session_id) {
          setResumeData(d.last_build);
        }
      })
      .catch(() => { });
  }, [activeConvoId]);

  useEffect(() => {
    if (taskId) setActiveTaskId(taskId);
  }, [taskId]);

  const handleSend = async (e?: React.FormEvent, retryPrompt?: string, files?: File[]) => {
    if (e) e.preventDefault();
    const prompt = retryPrompt || msgInput;
    if (!prompt.trim() && (!files || files.length === 0)) return;

    setOptimisticUserMsg({
      id: `temp-${Date.now()}`,
      role: "user",
      content: prompt,
      created_at: new Date().toISOString()
    });

    sendMessage(prompt, selectedProvider, selectedModel, files);
  };

  useEffect(() => {
    if (!isStreaming) {
      const t = setTimeout(() => setOptimisticUserMsg(null), 1000);
      return () => clearTimeout(t);
    }
  }, [isStreaming]);

  // Once backend confirms the user message is saved AND refetch completes,
  // we immediately clear the optimistic bubble.
  useEffect(() => {
    const handleUserPersisted = () => {
      setOptimisticUserMsg(null);
    };
    window.addEventListener("chat:user_persisted", handleUserPersisted);
    return () => window.removeEventListener("chat:user_persisted", handleUserPersisted);
  }, []);

  // Global listener for Markdown Button clicks
  useEffect(() => {
    const handleAction = (e: any) => {
      if (e.detail) {
        if (typeof e.detail === "string" && e.detail.startsWith("open_builder_")) {
          const sid = e.detail.replace("open_builder_", "");
          setBuilderSessionId(sid);
          setIsFocusMode(false);
          return;
        }
        handleSend(undefined, e.detail);
      }
    };
    window.addEventListener("chat:action", handleAction);
    return () => window.removeEventListener("chat:action", handleAction);
  }, [handleSend]);

  // Global listener for Builder Session start events
  useEffect(() => {
    const handleBuilderSession = (e: any) => {
      if (e.detail) {
        setBuilderSessionId(e.detail);
        setIsFocusMode(false);
      }
    };
    window.addEventListener("builder:session", handleBuilderSession);
    return () => window.removeEventListener("builder:session", handleBuilderSession);
  }, []);

  const showActivityPanel = (activeMode === 'Standard' || activeMode === 'Ultra');

  const displayMessages = [
    ...(messages || []),
    ...(optimisticUserMsg && (!messages || !messages.find((m: any) => m.content === optimisticUserMsg.content)) ? [optimisticUserMsg] : [])
  ];

  // Smart Trigger for Builder Panel
  useEffect(() => {
    const lastMsg = displayMessages[displayMessages.length - 1];
    if (lastMsg && lastMsg.role !== "user" && lastMsg.content) {
      const match = lastMsg.content.match(/(?:"session_id"\s*:\s*"([^"]+)"|Session:\s*`?(session_[a-zA-Z0-9]+)`?)/);
      if (match) {
        const sid = match[1] || match[2];
        if (sid) {
          setBuilderSessionId(sid);
          setIsFocusMode(false); // Pop it open next to chat
        }
      }
    }
  }, [displayMessages]);

  const resumeProject = () => {
    if (resumeData?.session_id) {
      setBuilderSessionId(resumeData.session_id);
    }
  };

  return (
    <>
      {/* Dynamic Multi-Panel Layout */}
      <main className={cn(
        "flex-1 flex gap-4 min-w-0 transition-all duration-500 ease-in-out",
        showActivityPanel || builderSessionId ? "pr-0" : ""
      )}>
        {/* Central Chat Node */}
        <div className={cn(
          "flex-1 min-w-0 h-full flex flex-col min-h-0 transition-all duration-500",
          isFocusMode && builderSessionId ? "w-0 hidden" : "flex"
        )}>
          {/* Resume UX Banner */}
          {resumeData && !builderSessionId && !dismissResume && (
            <div className="mx-4 mt-2 p-3 rounded-xl bg-primary/10 border border-primary/20 backdrop-blur-md flex flex-col sm:flex-row items-center justify-between gap-3 animate-in fade-in slide-in-from-top-4">
              <div className="flex items-center gap-3 text-sm">
                <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary">💼</div>
                <div>
                  <div className="font-bold text-foreground">I found your last project 👍</div>
                  <div className="text-white/60 text-xs">{resumeData.project_name || "DreamStore"} (v{resumeData.version || 1})</div>
                </div>
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={resumeProject} className="text-xs">Continue editing</Button>
                <a href={`/api/v1/builder/download/${resumeData.session_id}`} target="_blank" rel="noreferrer">
                  <Button size="sm" variant="outline" className="text-xs border-white/10 text-white hover:bg-white/10">Download it</Button>
                </a>
                <Button size="sm" variant="ghost" className="text-xs text-white/50 hover:text-white px-2" onClick={() => setDismissResume(true)}>✕ Dismiss</Button>
              </div>
            </div>
          )}
          <div className="flex justify-end mb-2 px-1 gap-2">
            {(resumeData?.session_id || builderSessionId) && (
              <button
                onClick={() => setBuilderSessionId(builderSessionId ? null : resumeData?.session_id)}
                className={cn(
                  "flex items-center gap-2 px-3 py-1.5 rounded-xl text-[10px] font-bold uppercase tracking-widest border transition-all duration-200",
                  builderSessionId 
                    ? "bg-primary/20 text-primary border-primary/40 shadow-[0_0_12px_rgba(0,240,255,0.2)]"
                    : "bg-white/5 text-white/40 border-white/10 hover:bg-primary/10 hover:text-primary hover:border-primary/30"
                )}
              >
                <MonitorPlay className="w-3.5 h-3.5" />
                {builderSessionId ? "Close Builder" : "Open Builder"}
              </button>
            )}
            <button
              onClick={() => setTraceOpen(o => !o)}
              className={cn(
                "flex items-center gap-2 px-3 py-1.5 rounded-xl text-[10px] font-bold uppercase tracking-widest border transition-all duration-200",
                traceOpen
                  ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/40 shadow-[0_0_12px_rgba(0,240,255,0.2)]"
                  : "bg-white/5 text-white/40 border-white/10 hover:bg-cyan-500/10 hover:text-cyan-400 hover:border-cyan-500/30"
              )}
            >
              <Activity className={cn("w-3.5 h-3.5", isStreaming && "animate-pulse text-cyan-400")} />
              {isStreaming ? "Live Trace" : "🔍 Trace"}
              {isStreaming && (
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
              )}
            </button>
          </div>

          <div className="flex-1 min-h-0 flex flex-col">
            <ChatContainer
              title={activeTitle}
              messages={displayMessages}
              liveMessage={liveMessage}
              isStreaming={isStreaming}
              errorMsg={errorMsg}
              msgInput={msgInput}
              setMsgInput={setMsgInput}
              onSend={handleSend}
              onCancel={cancelStream}
              isLoading={messagesLoading}
              availableProviders={availableProviders}
              selectedProvider={selectedProvider}
              setSelectedProvider={setSelectedProvider}
              selectedModel={selectedModel}
              setSelectedModel={setSelectedModel}
            />
          </div>
        </div>

        {/* Builder Panel (takes priority if active) */}
        {builderSessionId ? (
          <div className={cn(
            "h-full flex-shrink-0 animate-in slide-in-from-right-8 duration-500 ease-out",
            isFocusMode ? "w-full" : "w-[50vw] xl:w-[60vw]"
          )}>
            <div className="h-full rounded-2xl overflow-hidden shadow-2xl shadow-black/50">
              <BuilderPanel
                sessionId={builderSessionId}
                onClose={() => setBuilderSessionId(null)}
                isFocusMode={isFocusMode}
                setFocusMode={setIsFocusMode}
              />
            </div>
          </div>
        ) : (
          /* Right Panel - Agent Activity (Advanced Modes) */
          showActivityPanel && (
            <div className="w-80 h-full flex-shrink-0 animate-in slide-in-from-right-8 duration-500 ease-out hidden xl:block">
              <div className="h-full rounded-2xl overflow-hidden border border-white/10 shadow-2xl shadow-black/50">
                <LiveExecutionPanel
                  messages={displayMessages}
                  isStreaming={isStreaming}
                  liveMessage={liveMessage}
                />
              </div>
            </div>
          )
        )}
      </main>

      {/* Agent Trace Panel Overlay */}
      <AgentTracePanel
        taskId={activeTaskId}
        isOpen={traceOpen}
        onClose={() => setTraceOpen(false)}
      />
    </>
  );
}

function NewConversationModal({ isOpen, onClose, onSelect }: { isOpen: boolean, onClose: () => void, onSelect: (id: number) => void }) {
  const { data: agents } = useListAgents();
  const { register, handleSubmit, reset, setValue } = useForm();

  useEffect(() => {
    if (agents && agents.length > 0) {
      setValue("agentId", agents[0].id);
    }
  }, [agents, setValue]);
  const queryClient = useQueryClient();
  const { mutate, isPending } = useCreateConversation({
    mutation: {
      onSuccess: (data: any) => {
        // Fix #18: use /api/v1/ queryKey + unwrap data if wrapped
        queryClient.invalidateQueries({ queryKey: ["/api/v1/conversations"] });
        const id = data?.data?.id ?? data?.id;
        if (id) onSelect(id);
        reset();
        onClose();
      }
    }
  });

  const onSubmit = (data: any) => mutate({ data: { title: data.title || "New Conversation", agentId: data.agentId } });

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Establish Secure Neural Link">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6 pt-2">
        <div className="space-y-2">
          <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest ml-1">Channel Identifier</label>
          <Input
            {...register("title")}
            placeholder="e.g. PROJECT_OMEGA_REPORT (or leave blank for auto-name)"
            className="bg-black/40 border-white/10"
          />
        </div>
        <div className="space-y-2">
          <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest ml-1">Select Operative</label>
          <select
            {...register("agentId", { required: true })}
            className="flex h-12 w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary appearance-none transition-all cursor-pointer hover:border-white/20"
          >
            {agents?.map((a: any) => <option key={a.id} value={a.id}>{a.name} [{a.model}]</option>)}
          </select>
        </div>
        <div className="flex justify-end gap-3 pt-6 border-t border-white/5">
          <Button type="button" variant="ghost" onClick={onClose} className="uppercase text-[10px] tracking-widest font-bold">Abort</Button>
          <Button type="submit" disabled={isPending} className="px-8 uppercase text-[10px] tracking-[0.2em] font-bold">
            {isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : "Initiate Connection"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
