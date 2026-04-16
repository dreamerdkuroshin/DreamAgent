import { useRef, useEffect, useState } from "react";
import { MessageBubble } from "./MessageBubble";
import { Loader2, MessageSquare, ShieldCheck, Zap, Brain, Network, XCircle, Paperclip, X, FolderOpen, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button, Input, Card } from "@/components/ui-elements";
import { useAppStore } from "@/store/app.store";
import { BuilderFormWidget } from "./BuilderFormWidget";

interface ChatContainerProps {
  title: string;
  messages: any[];
  liveMessage: any;
  isStreaming: boolean;
  errorMsg: string | null;
  msgInput: string;
  setMsgInput: (val: string) => void;
  onSend: (e?: React.FormEvent, retryPrompt?: string, files?: File[]) => void;
  onCancel: () => void;
  isLoading: boolean;
  availableProviders: any[];
  selectedProvider: string;
  setSelectedProvider: (v: string) => void;
  selectedModel: string;
  setSelectedModel: (v: string) => void;
}

const MODES = [
  { id: "Fast", label: "⚡ Fast", icon: Zap, active: "bg-emerald-400/20 border-emerald-400/50 text-emerald-400", desc: "Instant responses. May skip verification." },
  { id: "Truth", label: "🧠 Truth", icon: ShieldCheck, active: "bg-primary/20 border-primary/50 text-primary", desc: "Slower, but verifies sources, detects contradictions, and avoids hallucinations." },
];

export function ChatContainer({
  title,
  messages,
  liveMessage,
  isStreaming,
  errorMsg,
  msgInput,
  setMsgInput,
  onSend,
  onCancel,
  isLoading,
  availableProviders,
  selectedProvider,
  setSelectedProvider,
  selectedModel,
  setSelectedModel
}: ChatContainerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const { mode, setMode } = useAppStore();
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [showBuilderForm, setShowBuilderForm] = useState(false);

  // Listen for backend builder_form SSE event (dispatched via useChat)
  useEffect(() => {
    const handler = () => setShowBuilderForm(true);
    window.addEventListener("builder:form", handler);
    return () => window.removeEventListener("builder:form", handler);
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    setAttachedFiles(prev => {
      const existingNames = new Set(prev.map(f => f.name));
      return [...prev, ...files.filter(f => !existingNames.has(f.name))];
    });
    e.target.value = "";
  };

  const removeFile = (name: string) => {
    setAttachedFiles(prev => prev.filter(f => f.name !== name));
  };

  const handleSubmit = (e?: React.FormEvent, retryPrompt?: string) => {
    onSend(e, retryPrompt, attachedFiles.length > 0 ? attachedFiles : undefined);
    setAttachedFiles([]);
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, liveMessage]);

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0f0f13]/50 backdrop-blur-xl border border-white/5 rounded-2xl overflow-hidden shadow-2xl min-h-0">
      {/* Header */}
      <div className="p-4 border-b border-white/5 bg-black/40 flex items-center justify-between z-10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center neon-glow">
            <MessageSquare className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-foreground tracking-tight">{title}</h2>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="text-[10px] font-bold text-emerald-500/80 uppercase tracking-widest">Secure Link Active</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5 bg-black/40 p-1.5 rounded-xl border border-white/5 relative group">
          {MODES.map((m: any) => (
            <div key={m.id} className="relative group/btn">
              <button
                onClick={() => setMode(m.id as any)}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold border transition-all duration-300 uppercase tracking-wider",
                  mode === m.id
                    ? m.active
                    : "border-transparent text-muted-foreground hover:bg-white/5 hover:text-foreground"
                )}
              >
                {m.label}
              </button>
              {/* Tooltip */}
              <div className="absolute top-full right-0 mt-2 hidden group-hover/btn:block w-48 p-2 bg-black/90 border border-white/10 rounded-lg shadow-xl z-50 text-[10px] text-muted-foreground leading-tight">
                {m.desc}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Messages Area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 md:p-8 space-y-2 custom-scrollbar relative">
        {isLoading ? (
          <div className="flex h-full items-center justify-center">
            <div className="flex flex-col items-center gap-4">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
              <p className="text-xs font-mono text-primary/60 animate-pulse uppercase tracking-[0.2em]">Synchronizing Stream...</p>
            </div>
          </div>
        ) : !messages || messages.length === 0 ? (
          <div className="flex flex-col h-full items-center justify-center opacity-40">
            <Brain className="w-16 h-16 mb-4 text-primary" />
            <p className="text-sm font-mono tracking-widest uppercase">Comm Channel Empty</p>
          </div>
        ) : (
          messages.map((msg: any) => (
            <MessageBubble key={msg.id} message={msg} />
          ))
        )}

        {liveMessage && (
          <MessageBubble message={liveMessage} isStreaming={true} />
        )}

        {/* Inline Builder Form Widget — appears when backend sends builder_form event */}
        {showBuilderForm && (
          <div className="mr-auto w-full max-w-2xl animate-in fade-in slide-in-from-bottom-4 duration-500">
            <BuilderFormWidget
              onClose={() => setShowBuilderForm(false)}
              onSubmit={(prefs) => {
                setShowBuilderForm(false);
                // Send the JSON as a structured message so the backend gets the full prefs
                window.dispatchEvent(new CustomEvent("chat:action", {
                  detail: `Build this website: ${JSON.stringify(prefs)}`
                }));
              }}
            />
          </div>
        )}

        {errorMsg && (
          <div className="flex mr-auto max-w-[85%] mt-4 animate-in fade-in slide-in-from-top-4 duration-300">
             <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-200 flex flex-col gap-3 backdrop-blur-md">
                <p className="text-[10px] font-bold uppercase tracking-widest flex items-center gap-2 text-red-400">
                  <XCircle className="w-4 h-4"/> System Failure
                </p>
                <p className="text-sm opacity-80 leading-relaxed font-mono">{errorMsg}</p>
                <Button variant="outline" onClick={() => onSend(undefined, "Retry previous task")} className="mt-2 text-foreground border-white/10 hover:bg-white/5 py-1 px-3 text-[10px] h-8 uppercase font-bold tracking-wider">
                   Initialize Recovery Link
                </Button>
             </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="p-6 bg-black/40 border-t border-white/5 backdrop-blur-md relative z-10">
        <div className="max-w-4xl mx-auto mb-4 flex items-center gap-3">
          <div className="flex-1 relative">
            <select 
              value={`${selectedProvider}:${selectedModel}`}
              onChange={(e) => {
                const [p, m] = e.target.value.split(":");
                setSelectedProvider(p);
                setSelectedModel(m);
              }}
              className="w-full h-10 px-4 rounded-xl bg-white/5 border border-white/10 text-[11px] font-bold uppercase tracking-wider text-primary focus:outline-none focus:border-primary/50 appearance-none cursor-pointer hover:bg-white/10 transition-all"
            >
              {availableProviders.map(p => (
                <optgroup key={p.id} label={`${p.icon} ${p.name}`}>
                  {p.models.map((m: any) => (
                    <option key={m.id} value={`${p.id}:${m.id}`}>
                      {m.name} {m.tag ? `[${m.tag}]` : ""}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none opacity-40">
              <Zap className="w-3 h-3" />
            </div>
          </div>
        </div>

        <form onSubmit={(e) => {
          e.preventDefault();
          handleSubmit(e);
        }} className="relative flex flex-col max-w-4xl mx-auto w-full gap-2">

          {/* Attached Files Preview Bar */}
          {attachedFiles.length > 0 && (
            <div className="flex flex-wrap gap-2 px-2">
              {attachedFiles.map(file => (
                <div
                  key={file.name}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-primary/10 border border-primary/20 text-[10px] font-bold text-primary max-w-[180px] group"
                >
                  {file.type.startsWith("image/") ? (
                    <img src={URL.createObjectURL(file)} alt={file.name} className="w-4 h-4 rounded object-cover shrink-0" />
                  ) : (
                    <FileText className="w-3 h-3 shrink-0" />
                  )}
                  <span className="truncate">{file.name}</span>
                  <button
                    type="button"
                    onClick={() => removeFile(file.name)}
                    className="ml-1 opacity-40 hover:opacity-100 transition-opacity shrink-0"
                  >
                    <X className="w-2.5 h-2.5" />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="relative flex items-center w-full">
            {/* Hidden file inputs */}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={handleFileChange}
              accept="*/*"
            />
            <input
              ref={folderInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={handleFileChange}
              // @ts-ignore — webkitdirectory is non-standard but widely supported
              webkitdirectory=""
            />

            {/* Attachment trigger button */}
            <div className="absolute left-2.5 flex items-center gap-1 z-10">
              <div className="relative group">
                <button
                  type="button"
                  disabled={isStreaming}
                  className="p-1.5 rounded-lg text-muted-foreground hover:text-primary hover:bg-primary/10 transition-all disabled:opacity-30"
                  title="Attach files or folder"
                >
                  <Paperclip className="w-4 h-4" />
                </button>
                {/* Dropdown */}
                <div className="absolute bottom-full left-0 mb-2 hidden group-focus-within:flex group-hover:flex flex-col gap-1 bg-black/80 border border-white/10 rounded-xl p-1.5 backdrop-blur-xl shadow-2xl min-w-[140px] z-50">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-bold text-foreground hover:bg-primary/10 hover:text-primary transition-all text-left"
                  >
                    <FileText className="w-3.5 h-3.5" /> Attach Files
                  </button>
                  <button
                    type="button"
                    onClick={() => folderInputRef.current?.click()}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-bold text-foreground hover:bg-secondary/10 hover:text-secondary transition-all text-left"
                  >
                    <FolderOpen className="w-3.5 h-3.5" /> Attach Folder
                  </button>
                </div>
              </div>
            </div>

            <Input 
              value={msgInput}
              onChange={e => setMsgInput(e.target.value)}
              placeholder="Transmit high-level objective..."
              className="pl-12 pr-16 h-14 bg-white/5 rounded-2xl border-white/10 focus:border-primary/50 shadow-2xl placeholder:opacity-40"
              disabled={isStreaming}
            />
            {isStreaming ? (
              <button
                type="button"
                onClick={onCancel}
                className="absolute right-2.5 p-2.5 rounded-xl bg-red-500/20 text-red-500 hover:bg-red-500 hover:text-black hover:shadow-[0_0_20px_rgba(239,68,68,0.4)] transition-all active:scale-90 flex items-center justify-center"
                title="Stop Agent"
              >
                <XCircle className="w-5 h-5" />
              </button>
            ) : (
              <button 
                type="submit" 
                disabled={!msgInput.trim() && attachedFiles.length === 0}
                className="absolute right-2.5 p-2.5 rounded-xl bg-primary text-black disabled:opacity-30 hover:shadow-[0_0_20px_rgba(0,240,255,0.4)] transition-all active:scale-90"
              >
                <Network className="w-5 h-5" />
              </button>
            )}
          </div>
        </form>
        <div className="flex justify-center mt-3">
          <p className="text-[9px] text-muted-foreground uppercase tracking-[0.3em] opacity-30">Secure Multi-Agent Environment V1.0</p>
        </div>
      </div>
    </div>
  );
}
