import { useEffect, useRef, useState } from "react";
import { Terminal, Activity, Cpu, Database, Network, Shield, Zap, CheckCircle2, Loader2, Brain, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

// Map step types to display config
const STEP_CONFIG: Record<string, { color: string; bg: string; border: string; icon: any; label: string }> = {
  thinking:  { color: "text-amber-400",   bg: "bg-amber-500/5",   border: "border-amber-500/20",   icon: Brain,      label: "Planning"  },
  plan:      { color: "text-emerald-400", bg: "bg-emerald-500/5", border: "border-emerald-500/20", icon: ChevronRight,label: "Strategy"  },
  step:      { color: "text-cyan-400",    bg: "bg-cyan-500/5",    border: "border-cyan-500/20",    icon: Zap,        label: "Action"    },
  tool:      { color: "text-primary",     bg: "bg-primary/5",     border: "border-primary/20",     icon: Terminal,   label: "Tool"      },
  result:    { color: "text-blue-400",    bg: "bg-blue-500/5",    border: "border-blue-500/20",    icon: CheckCircle2,label: "Result"   },
  agent:     { color: "text-orange-400",  bg: "bg-orange-500/5",  border: "border-orange-500/20",  icon: Cpu,        label: "Agent"     },
  error:     { color: "text-red-400",     bg: "bg-red-500/5",     border: "border-red-500/20",     icon: Zap,        label: "Error"     },
  final:     { color: "text-emerald-400", bg: "bg-emerald-500/5", border: "border-emerald-500/20", icon: CheckCircle2,label: "Done"     },
};

function getStepConfig(type: string) {
  return STEP_CONFIG[type] ?? { color: "text-muted-foreground", bg: "bg-white/5", border: "border-white/10", icon: Terminal, label: type };
}

function useElapsedTimer(running: boolean) {
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef<number | null>(null);
  
  useEffect(() => {
    if (running) {
      startRef.current = Date.now();
      setElapsed(0);
      const id = setInterval(() => {
        setElapsed(Math.floor((Date.now() - (startRef.current ?? Date.now())) / 1000));
      }, 1000);
      return () => clearInterval(id);
    } else {
      startRef.current = null;
    }
  }, [running]);
  
  return elapsed;
}

export function LiveExecutionPanel({ 
  messages, 
  isStreaming,
  liveMessage 
}: { 
  messages: any[];
  isStreaming: boolean;
  liveMessage?: any;
}) {
  const logEndRef = useRef<HTMLDivElement>(null);
  const elapsed = useElapsedTimer(isStreaming);
  
  // Scroll to bottom on new steps
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [liveMessage?.steps?.length, isStreaming]);

  // Gather all live steps from the active liveMessage
  const liveSteps: any[] = liveMessage?.steps ?? [];
  const lastStep = liveSteps[liveSteps.length - 1];
  
  return (
    <div className="flex flex-col h-full overflow-hidden bg-black/60 backdrop-blur-3xl border-l border-white/5">
      {/* Header */}
      <div className="p-4 border-b border-white/10 flex items-center justify-between bg-[#0f0f13]/80">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-secondary animate-pulse" />
          <h3 className="text-[11px] font-bold text-foreground uppercase tracking-[0.2em]">Live Trace</h3>
        </div>
        {isStreaming && (
          <div className="flex items-center gap-2">
            <span className="text-[9px] font-mono text-emerald-400 font-bold uppercase tracking-wider tabular-nums">
              {elapsed}s
            </span>
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-ping" />
          </div>
        )}
      </div>

      {/* System Status Indicators */}
      <div className="p-4 grid grid-cols-2 gap-2 bg-[#0a0a0c]/40 border-b border-white/5">
        <StatusItem icon={<Cpu className="w-3 h-3"/>} label="Core Engine" value="Online" color="text-emerald-400" />
        <StatusItem icon={<Database className="w-3 h-3"/>} label="Neural Vector" value="Synced" color="text-blue-400" />
        <StatusItem icon={<Network className="w-3 h-3"/>} label="Node Mesh" value="Active" color="text-secondary" />
        <StatusItem icon={<Shield className="w-3 h-3"/>} label="Safety Guard" value="Verified" color="text-emerald-500" />
      </div>

      {/* Live Step Feed */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
        
        {/* Past messages as compact user/assistant rows */}
        {messages?.map((msg: any, i: number) => {
          const isUser = msg.role === "user";
          if (isUser) {
            return (
              <div key={`msg-${i}`} className="flex items-start gap-2 py-1 px-2 rounded border border-primary/10 bg-primary/5 animate-in fade-in duration-200">
                <span className="font-bold text-[10px] text-primary font-mono mt-0.5">&gt;&gt;</span>
                <span className="text-[10px] text-primary/80 truncate font-mono">
                  {msg.content?.substring(0, 50)}{(msg.content?.length ?? 0) > 50 ? "…" : ""}
                </span>
              </div>
            );
          }
          return null;
        })}

        {/* Live real-time step events */}
        {liveSteps.length === 0 && isStreaming && (
          <div className="flex items-center gap-2 py-2 px-3 rounded border border-amber-500/20 bg-amber-500/5 animate-pulse">
            <Loader2 className="w-3 h-3 animate-spin text-amber-400 flex-shrink-0" />
            <span className="text-[10px] text-amber-400 font-mono font-bold uppercase tracking-wider">Initializing agent...</span>
          </div>
        )}

        {liveSteps.map((step: any, i: number) => {
          const cfg = getStepConfig(step.type);
          const Icon = cfg.icon;
          const isLast = i === liveSteps.length - 1;
          
          return (
            <div 
              key={`step-${i}`}
              className={cn(
                "flex items-start gap-2 py-2 px-3 rounded border transition-all duration-300 animate-in fade-in slide-in-from-bottom-1",
                cfg.bg, cfg.border,
                isLast && isStreaming && "ring-1 ring-current/20"
              )}
            >
              <Icon className={cn("w-3 h-3 mt-0.5 flex-shrink-0", cfg.color, isLast && isStreaming && "animate-pulse")} />
              <div className="flex-1 min-w-0">
                <div className={cn("text-[9px] font-bold uppercase tracking-widest mb-0.5", cfg.color)}>
                  {cfg.label}{step.step !== undefined ? ` · step ${step.step + 1}` : ""}
                  {step.agent ? ` · ${step.agent}` : ""}
                  {step.tool ? ` · ${step.tool}` : ""}
                </div>
                <div className="text-[10px] text-foreground/70 font-mono leading-relaxed break-words">
                  {step.content}
                </div>
              </div>
              {isLast && isStreaming && step.type !== "final" && (
                <Loader2 className="w-2.5 h-2.5 animate-spin text-muted-foreground/50 flex-shrink-0 mt-1" />
              )}
            </div>
          );
        })}

        {/* Streaming indicator at bottom */}
        {isStreaming && liveSteps.length > 0 && (
          <div className="flex items-center gap-2 py-1.5 px-3 text-emerald-400/60 animate-pulse">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span className="uppercase tracking-widest text-[9px] font-bold">Processing...</span>
            <span className="ml-auto text-[9px] font-mono tabular-nums">{elapsed}s elapsed</span>
          </div>
        )}

        <div ref={logEndRef} />
      </div>

      {/* Footer */}
      <div className="p-3 bg-black/40 border-t border-white/10 flex items-center justify-between text-[9px] font-mono text-muted-foreground/40 uppercase tracking-[0.2em]">
        <span>Steps: {liveSteps.length}</span>
        <span>{isStreaming ? `⏱ ${elapsed}s` : "Idle"}</span>
      </div>
    </div>
  );
}

function StatusItem({ icon, label, value, color }: { icon: React.ReactNode, label: string, value: string, color: string }) {
  return (
    <div className="flex flex-col gap-1 p-2 rounded border border-white/5 bg-black/20 group hover:border-white/10 transition-colors">
      <div className="flex items-center gap-1.5 text-[9px] text-muted-foreground/60 font-bold uppercase tracking-tight">
        {icon} {label}
      </div>
      <div className={cn("text-[10px] font-bold flex items-center gap-1.5", color)}>
        <span className="h-1 w-1 rounded-full bg-current" />
        {value}
      </div>
    </div>
  );
}
