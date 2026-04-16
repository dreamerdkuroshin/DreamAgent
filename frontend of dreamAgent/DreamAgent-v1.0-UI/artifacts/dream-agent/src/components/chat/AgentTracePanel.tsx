/**
 * AgentTracePanel.tsx
 *
 * Live debug panel showing every agent step trace in real-time.
 * Polls GET /api/trace/:taskId every 2 s while a task is running.
 *
 * Agent role → badge colour map:
 *   planner     → blue
 *   executor    → amber
 *   code_agent  → green
 *   search_agent→ sky
 *   math_agent  → violet
 *   critic      → rose
 *   memory      → purple
 *   orchestrator→ emerald (final)
 */
import { useEffect, useState, useRef } from "react";
import { X, Activity, ChevronDown, ChevronUp, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

// ─── Types ────────────────────────────────────────────────────────────────────

interface TraceStep {
  type: string;
  agent?: string;
  role?: string;
  status?: string;
  step?: number;
  attempt?: number;
  timestamp?: string;
  content: string;
}

interface TraceData {
  task_id: string;
  status: string;
  step_count: number;
  steps: TraceStep[];
}

// ─── Badge helpers ────────────────────────────────────────────────────────────

const ROLE_META: Record<string, { label: string; emoji: string; color: string; glow: string }> = {
  planner:      { label: "Planner",      emoji: "🧠", color: "bg-blue-500/20 text-blue-300 border-blue-500/30",    glow: "shadow-blue-500/30" },
  executor:     { label: "Executor",     emoji: "⚡", color: "bg-amber-500/20 text-amber-300 border-amber-500/30", glow: "shadow-amber-500/30" },
  code_agent:   { label: "CodeAgent",    emoji: "💻", color: "bg-green-500/20 text-green-300 border-green-500/30", glow: "shadow-green-500/30" },
  search_agent: { label: "SearchAgent",  emoji: "🔍", color: "bg-sky-500/20 text-sky-300 border-sky-500/30",       glow: "shadow-sky-500/30" },
  math_agent:   { label: "MathAgent",    emoji: "📐", color: "bg-violet-500/20 text-violet-300 border-violet-500/30", glow: "shadow-violet-500/30" },
  critic:       { label: "Critic",       emoji: "🔴", color: "bg-rose-500/20 text-rose-300 border-rose-500/30",    glow: "shadow-rose-500/30" },
  memory:       { label: "Memory",       emoji: "🟣", color: "bg-purple-500/20 text-purple-300 border-purple-500/30", glow: "shadow-purple-500/30" },
  orchestrator: { label: "Orchestrator", emoji: "✅", color: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30", glow: "shadow-emerald-500/30" },
};

function getRoleMeta(step: TraceStep) {
  const key = step.role || step.agent || step.type;
  return ROLE_META[key] ?? { label: key ?? "Agent", emoji: "🤖", color: "bg-white/10 text-white/70 border-white/20", glow: "shadow-white/10" };
}

function AgentBadge({ step }: { step: TraceStep }) {
  const meta = getRoleMeta(step);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-widest",
        meta.color
      )}
    >
      {meta.emoji} {meta.label}
    </span>
  );
}

// ─── Main Panel ───────────────────────────────────────────────────────────────

interface AgentTracePanelProps {
  taskId: string | null;
  isOpen: boolean;
  onClose: () => void;
}

export function AgentTracePanel({ taskId, isOpen, onClose }: AgentTracePanelProps) {
  const [trace, setTrace] = useState<TraceData | null>(null);
  const [loading, setLoading] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<number, boolean>>({});
  const bottomRef = useRef<HTMLDivElement>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchTrace = async () => {
    if (!taskId) return;
    try {
      const res = await fetch(`/api/trace/${taskId}`);
      if (res.ok) {
        const data: TraceData = await res.json();
        setTrace(data);
      }
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    if (!isOpen || !taskId) return;
    setLoading(true);
    fetchTrace().finally(() => setLoading(false));

    intervalRef.current = setInterval(async () => {
      await fetchTrace();
      if (trace?.status && ["completed", "error", "cancelled"].includes(trace.status)) {
        clearInterval(intervalRef.current!);
      }
    }, 2000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isOpen, taskId]);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [trace?.step_count]);

  if (!isOpen) return null;

  const isRunning = trace?.status === "running" || !trace?.status;
  const isDone = trace?.status === "completed";
  const isError = trace?.status === "error";

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end pointer-events-none"
      aria-label="Agent Trace Panel"
    >
      {/* Backdrop (click to close) */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm pointer-events-auto"
        onClick={onClose}
      />

      {/* Panel */}
      <aside
        className={cn(
          "relative pointer-events-auto w-full max-w-md h-full flex flex-col",
          "bg-[#0a0a0f]/95 border-l border-white/10 shadow-2xl",
          "animate-in slide-in-from-right-8 duration-300"
        )}
      >
        {/* ── Header ── */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10 bg-white/5">
          <div className="flex items-center gap-3">
            <div className={cn(
              "w-2.5 h-2.5 rounded-full",
              isRunning ? "bg-cyan-400 animate-pulse shadow-[0_0_8px_rgba(0,240,255,0.8)]"
                : isDone ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.6)]"
                : isError ? "bg-rose-400"
                : "bg-white/30"
            )} />
            <span className="text-xs font-bold text-white uppercase tracking-[0.15em]">
              Agent Trace
            </span>
            {trace && (
              <span className={cn(
                "text-[9px] font-mono px-2 py-0.5 rounded-full border uppercase",
                isRunning ? "text-cyan-300 border-cyan-500/30 bg-cyan-500/10"
                  : isDone ? "text-emerald-300 border-emerald-500/30 bg-emerald-500/10"
                  : "text-rose-300 border-rose-500/30 bg-rose-500/10"
              )}>
                {trace.status}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setTrace(null); fetchTrace(); }}
              className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/10 transition-all"
              title="Refresh"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-white/40 hover:text-rose-400 hover:bg-rose-500/10 transition-all"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* ── Stats bar ── */}
        {trace && (
          <div className="flex items-center gap-4 px-5 py-2.5 border-b border-white/5 bg-black/20 text-[10px] font-mono text-white/40">
            <span>TASK <span className="text-white/60">{trace.task_id?.slice(0, 8)}…</span></span>
            <span>STEPS <span className="text-cyan-400">{trace.step_count}</span></span>
          </div>
        )}

        {/* ── Step List ── */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-2 custom-scrollbar">
          {loading && !trace?.steps?.length && (
            <div className="flex flex-col items-center justify-center h-40 gap-3 text-white/30">
              <Activity className="w-6 h-6 animate-pulse" />
              <span className="text-[10px] font-mono uppercase tracking-widest">Awaiting trace…</span>
            </div>
          )}

          {!taskId && (
            <div className="flex flex-col items-center justify-center h-40 gap-2 text-white/30">
              <Activity className="w-6 h-6 opacity-30" />
              <span className="text-[10px] font-mono uppercase tracking-widest">No active task</span>
            </div>
          )}

          {trace?.steps?.map((step, i) => {
            const meta = getRoleMeta(step);
            const isCollapsed = collapsed[i];
            const isFinal = step.type === "final";
            const isCritic = step.role === "critic" || step.agent === "critic";
            const isRetry = isCritic && step.status === "retry";

            return (
              <div
                key={i}
                className={cn(
                  "rounded-xl border p-3 transition-all duration-200",
                  isFinal
                    ? "border-emerald-500/40 bg-emerald-500/5 shadow-lg shadow-emerald-500/10"
                    : isRetry
                    ? "border-rose-500/30 bg-rose-500/5"
                    : "border-white/8 bg-white/3 hover:bg-white/5"
                )}
              >
                {/* Step header */}
                <div
                  className="flex items-start justify-between gap-2 cursor-pointer"
                  onClick={() => setCollapsed(c => ({ ...c, [i]: !c[i] }))}
                >
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] font-mono text-white/25">#{i + 1}</span>
                    <AgentBadge step={step} />
                    {step.attempt && step.attempt > 1 && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded-full border border-rose-500/30 bg-rose-500/10 text-rose-400 font-bold">
                        RETRY {step.attempt}
                      </span>
                    )}
                    {step.status && (
                      <span className={cn(
                        "text-[9px] font-mono",
                        step.status === "done" || step.status === "valid" || step.status === "saved"
                          ? "text-emerald-400"
                          : step.status === "running"
                          ? "text-cyan-400 animate-pulse"
                          : step.status === "retry"
                          ? "text-rose-400"
                          : "text-white/30"
                      )}>
                        {step.status.toUpperCase()}
                      </span>
                    )}
                  </div>
                  <button className="text-white/20 hover:text-white/60 flex-shrink-0 mt-0.5">
                    {isCollapsed ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />}
                  </button>
                </div>

                {/* Step content */}
                {!isCollapsed && (
                  <div className="mt-2.5 space-y-1">
                    <p className="text-[11px] text-white/70 leading-relaxed">{step.content}</p>
                    {step.timestamp && (
                      <p className="text-[9px] font-mono text-white/20 mt-1">
                        {new Date(step.timestamp).toLocaleTimeString()}
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {/* Running indicator */}
          {isRunning && trace && (
            <div className="flex items-center gap-2 px-3 py-2 text-cyan-400/60">
              <div className="flex gap-1">
                {[0,1,2].map(i => (
                  <div
                    key={i}
                    className="w-1 h-1 rounded-full bg-cyan-400 animate-bounce"
                    style={{ animationDelay: `${i * 150}ms` }}
                  />
                ))}
              </div>
              <span className="text-[10px] font-mono uppercase tracking-widest">Agents running…</span>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* ── Footer ── */}
        <div className="px-5 py-3 border-t border-white/5 bg-black/20 flex items-center gap-2">
          <div className="flex flex-wrap gap-2">
            {Object.entries(ROLE_META).map(([, meta]) => (
              <span key={meta.label} className={cn(
                "inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] border",
                meta.color
              )}>
                {meta.emoji} {meta.label}
              </span>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}
