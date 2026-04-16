import { CheckCircle2, Cog, Lightbulb, Search, Terminal, Zap, Info, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

// --- Specialized Card Components ---

function ThoughtBlock({ content, isLast }: { content: string; isLast: boolean }) {
  return (
    <div className={cn(
      "p-3 rounded-xl border border-emerald-500/10 bg-emerald-500/5 space-y-2",
      isLast && "ring-1 ring-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.05)]"
    )}>
      <div className="flex items-center gap-2 text-emerald-400 font-semibold text-[10px] uppercase tracking-wider">
        <Lightbulb className="w-3 h-3" /> Strategy & Planning
      </div>
      <div className="text-xs text-emerald-100/70 leading-relaxed italic">
        "{content}"
      </div>
    </div>
  );
}

function ToolExecutionCard({ tool, content, isLast, status }: { tool?: string; content: string; isLast: boolean; status?: string }) {
  return (
    <div className={cn(
      "p-3 rounded-xl border border-primary/10 bg-primary/5 space-y-2 relative overflow-hidden",
      isLast && "border-primary/30 shadow-[0_0_15px_rgba(0,240,255,0.05)]"
    )}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-primary font-semibold text-[10px] uppercase tracking-wider">
          <Cog className={cn("w-3 h-3", (isLast && status !== 'done') && "animate-spin")} /> 
          Action: {tool || "System Command"}
        </div>
        {isLast && status !== 'done' && (
          <Badge variant="neon" className="text-[9px] py-0 h-4 border-primary/30 text-primary bg-primary/10 animate-pulse">Running</Badge>
        )}
      </div>
      <div className="text-xs text-primary-foreground/80 font-mono bg-black/40 p-2 rounded border border-white/5 truncate">
        {content}
      </div>
      {isLast && status !== 'done' && (
        <div className="absolute inset-0 bg-gradient-to-r from-primary/0 via-primary/5 to-primary/0 animate-shimmer" />
      )}
    </div>
  );
}

function ResultCard({ content }: { content: string }) {
  return (
    <div className="p-3 rounded-xl border border-blue-500/10 bg-blue-500/5 space-y-2">
      <div className="flex items-center gap-2 text-blue-400 font-semibold text-[10px] uppercase tracking-wider">
        <Terminal className="w-3 h-3" /> Observation
      </div>
      <div className="text-[11px] text-blue-100/60 line-clamp-3 font-mono">
        {content}
      </div>
    </div>
  );
}

function ReflectionCard({ content }: { content: string }) {
  return (
    <div className="p-3 rounded-xl border border-purple-500/10 bg-purple-500/5 space-y-2">
      <div className="flex items-center gap-2 text-purple-400 font-semibold text-[10px] uppercase tracking-wider">
        <CheckCircle2 className="w-3 h-3" /> Synthesis
      </div>
      <div className="text-xs text-purple-100/70 leading-relaxed font-medium">
        {content}
      </div>
    </div>
  );
}

function AgentStatusCard({ agent, content, status, isLast }: { agent?: string; content: string; status?: string; isLast: boolean }) {
  const isDone = status === 'done';
  return (
    <div className={cn(
      "p-3 rounded-xl border border-orange-500/10 bg-orange-500/5 space-y-2",
      isLast && !isDone && "ring-1 ring-orange-500/30"
    )}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-orange-400 font-semibold text-[10px] uppercase tracking-wider">
          <Zap className={cn("w-3 h-3", isLast && !isDone && "animate-pulse")} /> 
          {agent || "Sub-Agent"} Dispatch
        </div>
        {isDone ? (
          <CheckCircle2 className="w-3 h-3 text-emerald-400" />
        ) : (
          <Loader2 className="w-3 h-3 animate-spin text-orange-400" />
        )}
      </div>
      <div className="text-xs text-orange-100/70">
        {content}
      </div>
    </div>
  );
}

// --- Main Components ---

import { Badge } from "@/components/ui-elements";
import { Loader2 } from "lucide-react";

export function ThinkingSteps({ steps }: { steps: any[] }) {
  if (!steps || steps.length === 0) return null;

  return (
    <div className="my-4 space-y-3">
      {steps.map((step, i) => {
        const isLast = i === steps.length - 1;
        
        switch (step.type) {
          case "plan": 
            return <ThoughtBlock key={i} content={step.content} isLast={isLast} />;
          case "tool": 
            return <ToolExecutionCard key={i} tool={step.tool} content={step.content} isLast={isLast} status={step.status} />;
          case "result": 
            return <ResultCard key={i} content={step.content} />;
          case "reflection": 
            return <ReflectionCard key={i} content={step.content} />;
          case "agent":
            return <AgentStatusCard key={i} agent={step.agent} content={step.content} status={step.status} isLast={isLast} />;
          default:
            return (
              <div key={i} className="flex items-center gap-2 text-[10px] text-muted-foreground opacity-50 px-2">
                <Info className="w-3 h-3" /> {step.content}
              </div>
            );
        }
      })}
    </div>
  );
}
