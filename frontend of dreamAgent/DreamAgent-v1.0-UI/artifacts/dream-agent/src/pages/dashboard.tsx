import { useState } from "react";
import { useGetStats, useListTasks, useListConversations } from "@workspace/api-client-react";
import { Layout } from "@/components/layout";
import { Card, Badge, Button } from "@/components/ui-elements";
import {
  Activity, Users, CheckCircle, Zap, Clock, MessageSquare, Plus, Loader2,
  Cpu, Brain, BarChart3, DollarSign, Network, TrendingUp, AlertTriangle,
  Layers, ListChecks, Sparkles, RefreshCw, GitBranch
} from "lucide-react";
import { Link } from "wouter";
import { formatDate } from "@/lib/utils";
import { cn } from "@/lib/utils";

const MODES = [
  {
    id: "Lite", label: "Lite", sub: "Single-shot call · No memory",
    icon: Zap, color: "text-emerald-400",
    active: "bg-emerald-400/20 border-emerald-400/50",
    glow: "shadow-[0_0_20px_rgba(52,211,153,0.15)]",
  },
  {
    id: "Standard", label: "Standard", sub: "AI + short/long-term memory",
    icon: Brain, color: "text-primary",
    active: "bg-primary/20 border-primary/50",
    glow: "shadow-[0_0_20px_rgba(0,240,255,0.15)]",
  },
  {
    id: "Ultra", label: "Ultra", sub: "Orchestrator → Planner → Worker → ReAct",
    icon: Network, color: "text-secondary",
    active: "bg-secondary/20 border-secondary/50",
    glow: "shadow-[0_0_20px_rgba(139,92,246,0.15)]",
  },
];

const LOOP_TYPES = [
  { id: "ReAct", color: "text-primary", desc: "Reasoning + Acting" },
  { id: "AutoGPT", color: "text-secondary", desc: "Goal-driven loop" },
  { id: "Tree of Thought", color: "text-amber-400", desc: "Multi-branch reasoning" },
];

const SELF_IMPROVE_STATS = [
  { label: "Total Runs", value: "142", icon: RefreshCw, color: "text-primary" },
  { label: "Success Rate", value: "89.4%", icon: TrendingUp, color: "text-emerald-400" },
  { label: "Avg Time", value: "4.2s", icon: Clock, color: "text-amber-400" },
  { label: "Failures Logged", value: "15", icon: AlertTriangle, color: "text-red-400" },
];

export default function Dashboard() {
  const [activeMode, setActiveMode] = useState("Standard");
  const { data: stats, isLoading: statsLoading } = useGetStats();
  const { data: tasks, isLoading: tasksLoading } = useListTasks();
  const { data: conversations, isLoading: convosLoading } = useListConversations();
  const recentTasks = tasks?.slice(0, 5) || [];
  const recentConvos = conversations?.slice(0, 5) || [];

  return (
    <Layout>
      {/* Header */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-display font-bold text-foreground">Command Center</h1>
          <p className="text-muted-foreground mt-1">DreamAgent v1.0 · AI workforce at a glance.</p>
        </div>
        <div className="flex gap-3">
          <Link href="/agents" className="inline-flex items-center justify-center px-4 py-2 text-sm rounded-xl font-semibold bg-primary text-black hover:bg-primary/90 shadow-[0_0_15px_rgba(0,240,255,0.3)] transition-all">
            <Plus className="w-4 h-4 mr-2" /> New Agent
          </Link>
          <Link href="/tasks" className="inline-flex items-center justify-center px-4 py-2 text-sm rounded-xl font-semibold border-2 border-primary/50 text-primary hover:bg-primary/10 transition-all">
            <Zap className="w-4 h-4 mr-2" /> Deploy Task
          </Link>
        </div>
      </div>

      {/* Mode Selector */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-3">
          <Brain className="w-4 h-4 text-muted-foreground" />
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">Execution Mode</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {MODES.map((m: any) => (
            <button key={m.id} onClick={() => setActiveMode(m.id)} className={cn(
              "relative text-left p-4 rounded-xl border transition-all duration-200",
              activeMode === m.id ? `${m.active} ${m.glow}` : "bg-black/20 border-white/5 hover:border-white/10"
            )}>
              <div className="flex items-center gap-2 mb-1">
                <m.icon className={cn("w-4 h-4", m.color)} />
                <span className={cn("font-display font-bold text-sm", activeMode === m.id ? m.color : "text-foreground")}>{m.label} Mode</span>
                {activeMode === m.id && <span className={cn("ml-auto w-1.5 h-1.5 rounded-full", m.color.replace("text-","bg-"))} />}
              </div>
              <div className="text-xs text-muted-foreground">{m.sub}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Agent Loop Types */}
      <div className="mb-6 p-4 rounded-xl bg-black/20 border border-white/5">
        <div className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-3 flex items-center gap-2">
          <GitBranch className="w-3.5 h-3.5" /> Agent Loop Systems
        </div>
        <div className="flex flex-wrap gap-4">
          {LOOP_TYPES.map((l: any) => (
            <div key={l.id} className="flex items-center gap-2">
              <span className={cn("w-2 h-2 rounded-full", l.color.replace("text-","bg-"))} />
              <span className={cn("text-sm font-semibold", l.color)}>{l.id}</span>
              <span className="text-xs text-muted-foreground">— {l.desc}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Core Stats */}
      {statsLoading ? (
        <div className="flex justify-center p-12"><Loader2 className="w-8 h-8 animate-spin text-primary" /></div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard title="Active Agents" value={stats?.activeAgents || 0} total={stats?.totalAgents || 0} icon={Users} color="text-primary" />
          <StatCard title="Pending Tasks" value={stats?.pendingTasks || 0} total={stats?.totalTasks || 0} icon={Clock} color="text-amber-400" />
          <StatCard title="Completed" value={stats?.completedTasks || 0} icon={CheckCircle} color="text-emerald-400" />
          <StatCard title="Conversations" value={stats?.totalConversations || 0} icon={MessageSquare} color="text-secondary" />
        </div>
      )}

      {/* Token / Cost / Memory */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <Card className="p-4 flex items-center gap-4">
          <div className="p-2 rounded-lg bg-primary/10"><BarChart3 className="w-5 h-5 text-primary" /></div>
          <div>
            <div className="text-xs text-muted-foreground">Tokens (Session)</div>
            <div className="text-xl font-bold font-mono text-foreground">12,480</div>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-2 rounded-lg bg-amber-400/10"><DollarSign className="w-5 h-5 text-amber-400" /></div>
          <div>
            <div className="text-xs text-muted-foreground">Est. Cost (Session)</div>
            <div className="text-xl font-bold font-mono text-foreground">$0.037</div>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4">
          <div className="p-2 rounded-lg bg-emerald-400/10"><Layers className="w-5 h-5 text-emerald-400" /></div>
          <div>
            <div className="text-xs text-muted-foreground">Memory Entries</div>
            <div className="text-xl font-bold font-mono text-foreground">48 / 1000</div>
          </div>
        </Card>
      </div>

      {/* Self-Improvement Engine (v9) */}
      <Card className="p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display font-semibold text-base flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-secondary" /> Self-Improvement Engine <span className="text-xs text-muted-foreground font-normal ml-1">v9</span>
          </h3>
          <Link href="/monitoring" className="text-xs text-secondary hover:underline">View Details</Link>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {SELF_IMPROVE_STATS.map((s: any) => (
            <div key={s.label} className="bg-black/30 p-3 rounded-xl border border-white/5 flex items-center gap-3">
              <s.icon className={cn("w-4 h-4 flex-shrink-0", s.color)} />
              <div>
                <div className="text-xs text-muted-foreground">{s.label}</div>
                <div className={cn("font-bold font-mono text-sm", s.color)}>{s.value}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Task Queue Status */}
      <Card className="p-5 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-display font-semibold text-base flex items-center gap-2">
            <ListChecks className="w-4 h-4 text-amber-400" /> Task Queue
          </h3>
          <span className="text-xs text-emerald-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block animate-pulse" /> 2 workers running
          </span>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "Pending", value: stats?.pendingTasks || 3, color: "text-amber-400" },
            { label: "Running", value: 1, color: "text-primary" },
            { label: "Completed", value: stats?.completedTasks || 6, color: "text-emerald-400" },
          ].map(q => (
            <div key={q.label} className="text-center py-3 rounded-xl bg-black/30 border border-white/5">
              <div className={cn("text-2xl font-bold font-mono", q.color)}>{q.value}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{q.label}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* Recent Tasks & Convos */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-6">
          <div className="flex items-center justify-between mb-5">
            <h3 className="font-display font-semibold text-base flex items-center gap-2">
              <Activity className="w-4 h-4 text-primary" /> Recent Operations
            </h3>
            <Link href="/history" className="text-xs text-primary hover:underline">View All</Link>
          </div>
          {tasksLoading ? (
            <div className="h-32 flex items-center justify-center"><Loader2 className="w-5 h-5 animate-spin text-muted-foreground" /></div>
          ) : recentTasks.length === 0 ? (
            <div className="h-32 flex flex-col items-center justify-center text-muted-foreground">
              <CheckCircle className="w-7 h-7 mb-2 opacity-40" /><p className="text-sm">No operations yet</p>
            </div>
          ) : (
            <div className="space-y-2">
              {recentTasks.map((task: any) => (
                <div key={task.id} className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5 hover:border-primary/20 transition-colors">
                  <div>
                    <div className="font-medium text-sm text-foreground">{task.title}</div>
                    <div className="text-xs text-muted-foreground">{task.agentName} · {task.priority}</div>
                  </div>
                  <Badge variant={task.status === "completed" ? "success" : task.status === "running" ? "neon" : task.status === "failed" ? "error" : "warning"}>
                    {task.status}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card className="p-6">
          <div className="flex items-center justify-between mb-5">
            <h3 className="font-display font-semibold text-base flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-secondary" /> Agent Comms
            </h3>
            <Link href="/chat" className="text-xs text-secondary hover:underline">Open Chat</Link>
          </div>
          {convosLoading ? (
            <div className="h-32 flex items-center justify-center"><Loader2 className="w-5 h-5 animate-spin text-muted-foreground" /></div>
          ) : recentConvos.length === 0 ? (
            <div className="h-32 flex flex-col items-center justify-center text-muted-foreground">
              <MessageSquare className="w-7 h-7 mb-2 opacity-40" /><p className="text-sm">No conversations</p>
            </div>
          ) : (
            <div className="space-y-2">
              {recentConvos.map((convo: any) => (
                <div key={convo.id} className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5 hover:border-secondary/20 transition-colors">
                  <div>
                    <div className="font-medium text-sm text-foreground">{convo.title}</div>
                    <div className="text-xs text-muted-foreground">{convo.agentName} · {formatDate(convo.updatedAt)}</div>
                  </div>
                  <div className="text-xs bg-white/10 px-2 py-1 rounded-md text-muted-foreground">{convo.messageCount} msgs</div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </Layout>
  );
}

function StatCard({ title, value, total, icon: Icon, color }: any) {
  return (
    <Card className="p-5 relative overflow-hidden">
      <div className="flex justify-between items-start mb-3">
        <div className="p-2 rounded-lg bg-white/5"><Icon className={`w-5 h-5 ${color}`} /></div>
        {total !== undefined && <span className="text-xs text-muted-foreground">/ {total}</span>}
      </div>
      <div className="text-3xl font-display font-bold text-foreground">{value}</div>
      <div className="text-xs text-muted-foreground mt-1">{title}</div>
      <div className={`absolute -bottom-6 -right-6 w-20 h-20 rounded-full blur-2xl opacity-15 ${color.replace("text-", "bg-")}`} />
    </Card>
  );
}
