import { useState, useEffect, useRef } from "react";
import { ThinkingSteps } from "./ThinkingSteps";
import { Sparkles, ChevronDown, ChevronRight, Loader2, CheckCircle2, AlertCircle, Zap, Clock } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui-elements";
import { NewsAnalystCard } from "./NewsAnalystCard";

const extractNewsCluster = (content: string) => {
  if (!content) return { data: null, rest: "" };
  const match = content.match(/```json:news_cluster\n([\s\S]*?)```/);
  if (match) {
    try {
      const data = JSON.parse(match[1]);
      const rest = content.replace(match[0], "");
      return { data, rest };
    } catch {
      return { data: null, rest: content };
    }
  }
  return { data: null, rest: content };
};

const renderContent = (content: string) => {
  if (!content) return null;
  const regex = /\[([^\]]+)\]\(((?:https?:\/\/|action:)[^\s)]+)\)/g;
  const parts = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push(<span key={`text-${lastIndex}`}>{content.substring(lastIndex, match.index)}</span>);
    }

    const isAction = match[2].startsWith("action:");
    const isButton = isAction || match[1].includes("🔘") || content.substring(match.index - 5, match.index).includes("---");

    const matchUrl = match[2];
    const matchText = match[1];
    const matchIdx = match.index;
    parts.push(
      <a
        key={`link-${matchIdx}`}
        href={matchUrl}
        onClick={isAction ? (e) => {
          e.preventDefault();
          window.dispatchEvent(new CustomEvent("chat:action", { detail: matchUrl.replace("action:", "").trim() }));
        } : undefined}
        target={isAction ? undefined : "_blank"}
        rel="noopener noreferrer"
        className={cn(
          "inline-flex items-center gap-1.5 transition-colors no-underline cursor-pointer",
          isButton
            ? "bg-primary/20 hover:bg-primary/30 text-primary border border-primary/30 rounded-md px-3 py-1.5 text-xs font-bold shadow-sm shadow-primary/5 mt-2 mr-2 group/btn"
            : "text-primary hover:text-primary/80 underline decoration-primary/30 underline-offset-2"
        )}
      >
        {matchText.replace(/^🔘\s*/, "").trim()}
        {isButton && <ChevronRight className="w-3 h-3 group-hover/btn:translate-x-0.5 transition-transform" />}
      </a>
    );
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < content.length) {
    parts.push(<span key={`text-${lastIndex}`}>{content.substring(lastIndex)}</span>);
  }
  return parts.length > 0 ? <div className="flex flex-wrap items-center">{parts}</div> : content;
};

export function AgentMessage({ message, isStreaming = false }: { message: any; isStreaming?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef<number>(Date.now());

  useEffect(() => {
    if (!isStreaming) return;
    startRef.current = Date.now();
    setElapsed(0);
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [isStreaming]);

  // Only show reasoning panel if there are actual planning/agent steps
  // Don't show steps for simple token streams (instant/fast/simple paths)
  const hasAgentSteps = message.steps && message.steps.some(
    (s: any) => ["thinking", "plan", "step", "tool", "result", "agent"].includes(s.type) &&
      s.content && !s.content.startsWith("⚡") && !s.content.startsWith("💬")
  );
  const isError = !!message.error || (message.steps && message.steps.some((s: any) => s.type === 'error'));
  const isComplete = message.status === 'completed' || (!isStreaming && !isError && message.content);
  const isThinking = isStreaming && !isComplete && !isError;

  const { data: newsData, rest: mainContent } = extractNewsCluster(message.content || "");

  // True when we're streaming a news-type message but haven't parsed the cluster block yet
  const isNewsStreaming = isStreaming && !newsData && (
    message.steps?.some((s: any) => s.content?.toLowerCase().includes("news") || s.content?.toLowerCase().includes("search")) ||
    message.content?.includes("```json:news_cluster")
  );


  return (
    <div className="flex mr-auto w-full max-w-[90%] lg:max-w-[80%] mb-4 group animate-in fade-in slide-in-from-left-4 duration-500">
      <div className="p-1 rounded-2xl bg-gradient-to-br from-white/10 to-white/5 border border-white/10 shadow-xl overflow-hidden w-full">
        <div className="bg-[#0f0f13]/90 rounded-[14px] p-4 flex flex-col gap-3">

          {/* Header & Status Badge */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-primary" />
              </div>
              <div>
                <div className="text-[11px] font-bold text-foreground/80 uppercase tracking-tighter">AI Operative</div>
                <div className="flex items-center gap-1.5 mt-0.5">
                  {isThinking && (
                    <Badge variant="warning" className="h-4 py-0 text-[9px] border-amber-500/30 text-amber-400 bg-amber-500/5 flex items-center gap-1">
                      <Loader2 className="w-2.5 h-2.5 animate-spin" /> Thinking...
                    </Badge>
                  )}
                  {isComplete && (
                    <Badge variant="success" className="h-4 py-0 text-[9px] border-emerald-500/30 text-emerald-400 bg-emerald-500/5 flex items-center gap-1">
                      <CheckCircle2 className="w-2.5 h-2.5" /> Task Completed
                    </Badge>
                  )}
                  {isError && (
                    <Badge variant="error" className="h-4 py-0 text-[9px] border-red-500/30 text-red-400 bg-red-500/5 flex items-center gap-1">
                      <AlertCircle className="w-2.5 h-2.5" /> Execution Error
                    </Badge>
                  )}
                </div>
              </div>
            </div>

            {/* Steps Toggle — only for real multi-step agent work */}
            {hasAgentSteps && (
              <button
                onClick={() => setExpanded(!expanded)}
                className="flex items-center gap-1 text-[10px] font-medium text-muted-foreground hover:text-primary transition-all px-2 py-1 rounded-md hover:bg-white/5 border border-transparent hover:border-white/10"
              >
                {expanded ? (
                  <>Hide Reasoning <ChevronDown className="w-3 h-3" /></>
                ) : (
                  <>Show Reasoning <ChevronRight className="w-3 h-3" /></>
                )}
              </button>
            )}
          </div>

          {/* Expanded Thinking UI — only for real agent steps */}
          {expanded && hasAgentSteps && (
            <div className="animate-in zoom-in-95 fade-in duration-300">
              <ThinkingSteps steps={message.steps.filter((s: any) =>
                ["thinking", "plan", "step", "tool", "result", "agent"].includes(s.type)
              )} />
            </div>
          )}

          {/* Collapsed Step Preview — only for real agent work, not instant/simple */}
          {!expanded && isStreaming && hasAgentSteps && message.steps && message.steps.length > 0 && (
            <div className="p-3 rounded-xl border border-white/5 bg-white/5 flex items-center gap-3 relative overflow-hidden group/step">
              <div className="flex items-center justify-center w-6 h-6 rounded-md bg-primary/10 text-primary">
                <Zap className="w-3.5 h-3.5 animate-pulse" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[10px] text-primary/70 font-bold uppercase tracking-widest mb-0.5 flex items-center gap-2">
                  Working...
                  <span className="flex items-center gap-1 text-muted-foreground/60 font-mono normal-case tracking-normal">
                    <Clock className="w-2.5 h-2.5" />
                    {elapsed}s
                  </span>
                </div>
                <div className="text-xs text-muted-foreground truncate">
                  {message.steps[message.steps.length - 1].content}
                </div>
              </div>
              <div className="absolute inset-x-0 bottom-0 h-0.5 bg-primary/20 overflow-hidden">
                <div className="h-full bg-primary w-full origin-left animate-shimmer-progress" />
              </div>
            </div>
          )}

          {/* Main Answer Content */}
          {(mainContent || newsData || isNewsStreaming) && (
            <div className={cn(
              "prose prose-invert prose-sm max-w-none text-foreground/90 leading-relaxed font-sans",
              isStreaming && "animate-in fade-in slide-in-from-top-2 duration-700"
            )}>
              {mainContent && <div className="whitespace-pre-wrap">{renderContent(mainContent.trim())}</div>}

              {/* Show skeleton while streaming news, real card when data arrives */}
              {(newsData || isNewsStreaming) && <NewsAnalystCard data={newsData} loading={isNewsStreaming && !newsData} />}

              {/* Output Attribution Footer */}
              {((message.provider && message.model) || (message.steps?.find((s: any) => s.type === "final")?.provider)) && (
                <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-end gap-2 text-[9px] text-muted-foreground w-full uppercase tracking-widest font-bold select-none cursor-default">
                  <span>Generated by</span>
                  <Badge variant="default" className="text-[9px] bg-white/5 border-white/10 px-2 py-0.5 rounded-md hover:bg-white/10 transition-colors">
                    {message.model || message.steps?.find((s: any) => s.type === "final")?.model}
                  </Badge>
                  <span className="opacity-50 mx-0.5">via</span>
                  <span className="text-primary/70">{message.provider || message.steps?.find((s: any) => s.type === "final")?.provider}</span>
                </div>
              )}
            </div>
          )}

          {/* Initial Loading State */}
          {isStreaming && !message.steps?.length && !message.content && (
            <div className="flex items-center gap-3 py-2">
              <div className="w-4 h-4 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
              <span className="text-muted-foreground text-xs font-medium tracking-tight">Initializing neural chains...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
