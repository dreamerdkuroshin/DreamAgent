import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Layout } from "@/components/layout";
import { Card, Button } from "@/components/ui-elements";
import {
  BarChart3, DollarSign, Cpu, Zap, AlertTriangle, CheckCircle,
  TrendingUp, Brain, RefreshCw, Wrench, Clock, Sparkles, ChevronDown, Loader2
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis
} from "recharts";
import { cn } from "@/lib/utils";

type MonTab = "overview" | "tokens" | "self-improve" | "tasks" | "builder";

const tokenData = [
  { model: "gpt-4-turbo", input: 4200, output: 1800 },
  { model: "gpt-4", input: 2100, output: 900 },
  { model: "claude-3-opus", input: 1500, output: 600 },
  { model: "claude-3-sonnet", input: 3200, output: 1100 },
  { model: "gemini-pro", input: 800, output: 400 },
];

const costData = [
  { service: "OpenAI", cost: 0.021 },
  { service: "Anthropic", cost: 0.009 },
  { service: "Tavily", cost: 0.002 },
  { service: "HuggingFace", cost: 0.001 },
];

const activityData = [
  { time: "00:00", tasks: 1, tokens: 800 },
  { time: "04:00", tasks: 0, tokens: 0 },
  { time: "08:00", tasks: 3, tokens: 3200 },
  { time: "12:00", tasks: 6, tokens: 5800 },
  { time: "16:00", tasks: 4, tokens: 4100 },
  { time: "20:00", tasks: 2, tokens: 2400 },
  { time: "Now", tasks: 1, tokens: 1180 },
];

const selfImproveTrend = [
  { run: 1, success: 60, time: 6.2, failures: 4 },
  { run: 2, success: 67, time: 5.8, failures: 3 },
  { run: 3, success: 72, time: 5.1, failures: 3 },
  { run: 4, success: 78, time: 4.7, failures: 2 },
  { run: 5, success: 83, time: 4.4, failures: 2 },
  { run: 6, success: 87, time: 4.3, failures: 1 },
  { run: 7, success: 89, time: 4.2, failures: 1 },
];

const toolUsageData = [
  { tool: "tavily_search", uses: 34, success: 94 },
  { tool: "python_executor", uses: 22, success: 87 },
  { tool: "filesystem", uses: 18, success: 100 },
  { tool: "calculator", uses: 12, success: 100 },
  { tool: "slack_tools", uses: 8, success: 75 },
];

const radarData = [
  { subject: "Planning", A: 88 },
  { subject: "Research", A: 92 },
  { subject: "Coding", A: 74 },
  { subject: "Writing", A: 85 },
  { subject: "Validation", A: 90 },
  { subject: "Debate", A: 70 },
];

const tooltipStyle = {
  backgroundColor: "rgba(0,0,0,0.9)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: "10px",
  color: "#fff",
  fontSize: "12px",
};

const FAILURE_LOGS = [
  { type: "ToolError", cause: "Tavily API rate limit exceeded", severity: 2, recs: ["Add retry with backoff", "Cache search results"] },
  { type: "ContextOverflow", cause: "Prompt exceeded 4096 token limit for gpt-4", severity: 3, recs: ["Implement context chunking", "Use gpt-4-turbo instead"] },
  { type: "SandboxTimeout", cause: "Python executor hit 30s timeout on data processing", severity: 2, recs: ["Optimize query logic", "Increase timeout to 60s"] },
];

export default function Monitoring() {
  const [activeTab, setActiveTab] = useState<MonTab>("overview");
  const tabs: { id: MonTab; label: string; icon: any }[] = [
    { id: "overview", label: "Overview", icon: BarChart3 },
    { id: "tokens", label: "Token Usage", icon: Cpu },
    { id: "self-improve", label: "Self-Improvement", icon: Sparkles },
    { id: "tasks", label: "Task Queue", icon: Clock },
    { id: "builder", label: "Builder & Deploy", icon: Wrench },
  ];

  const { data: stats } = useQuery({
    queryKey: ["/api/v1/stats"],
    queryFn: async () => {
      const res = await fetch("/api/v1/stats");
      if (!res.ok) return null; // Fail gracefully — don't block UI
      return res.json();
    },
    refetchInterval: 5000 // Poll every 5s for live dashboard
  });

  const { data: toolStats } = useQuery({
    queryKey: ["/api/v1/monitoring/tools"],
    queryFn: async () => {
      const res = await fetch("/api/v1/monitoring/tools");
      if (!res.ok) return null;
      const json = await res.json();
      return json.data;
    },
    refetchInterval: 10000
  });

  const { data: queueStats } = useQuery({
    queryKey: ["/api/system-status"],
    queryFn: async () => {
      const res = await fetch("/api/system-status");
      if (!res.ok) return null;
      const json = await res.json();
      return json.queues;
    },
    refetchInterval: 5000
  });

  // Derived metrics from live /api/v1/stats
  const totalTasks     = stats?.totalTasks    || 0;
  const totalRuns      = stats?.total_runs    || 0;
  const successRate    = stats?.success_rate  ? `${(stats.success_rate * 100).toFixed(1)}%` : "N/A";
  const avgTime        = stats?.avg_duration  ? `${stats.avg_duration.toFixed(1)}s` : "N/A";
  const completedTasks = stats?.completedTasks || 0;
  const pendingTasks   = stats?.pendingTasks   || queueStats?.TOTAL_BACKLOG || 0;
  const activeAgents   = stats?.activeAgents   || 0;
  const deadLetterCount = stats?.queue?.dead    || queueStats?.dead_letter || 0;
  const buildSessions  = stats?.build_sessions || 0;
  const successBuilds  = stats?.successful_builds || 0;
  const failBuilds     = stats?.failed_builds  || 0;
  const avgFixAttempts = stats?.avg_fix_attempts || 0;

  return (
    <Layout>
      <div className="mb-6">
        <h1 className="text-3xl font-display font-bold text-foreground">Monitoring</h1>
        <p className="text-muted-foreground mt-1">Token usage, cost, agent performance, and self-improvement analytics.</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {tabs.map((t: any) => (
          <button key={t.id} onClick={() => setActiveTab(t.id)}
            className={cn("flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all",
              activeTab === t.id
                ? "bg-primary/15 text-primary border border-primary/30 shadow-[0_0_15px_rgba(0,240,255,0.1)]"
                : "text-muted-foreground hover:bg-white/5 border border-transparent"
            )}>
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {activeTab === "overview" && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCard icon={BarChart3} color="text-primary" label="Total Tasks" value={totalTasks} sub="all" />
            <KpiCard icon={Zap} color="text-amber-400" label="Swarm Runs" value={totalRuns} sub="v9 engine" />
            <KpiCard icon={Cpu} color="text-secondary" label="Active Agents" value={activeAgents} sub="online" />
            <KpiCard icon={TrendingUp} color="text-emerald-400" label="Success Rate" value={successRate} sub="swarm" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="p-6">
              <h3 className="font-display font-semibold text-sm mb-4 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-primary" /> Token Usage by Model
              </h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={tokenData} barGap={4}>
                  <XAxis dataKey="model" tick={{ fill: "#888", fontSize: 9 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fill: "#888", fontSize: 10 }} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(255,255,255,0.02)" }} />
                  <Bar dataKey="input" name="Input" fill="rgba(0,240,255,0.6)" radius={[3,3,0,0]} />
                  <Bar dataKey="output" name="Output" fill="rgba(139,92,246,0.6)" radius={[3,3,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <Card className="p-6">
              <h3 className="font-display font-semibold text-sm mb-4 flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-amber-400" /> Cost by Service
              </h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={costData} layout="vertical">
                  <XAxis type="number" tick={{ fill: "#888", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `$${v.toFixed(3)}`} />
                  <YAxis dataKey="service" type="category" tick={{ fill: "#bbb", fontSize: 11 }} tickLine={false} axisLine={false} width={65} />
                  <Tooltip contentStyle={tooltipStyle} formatter={(v: any) => [`$${Number(v).toFixed(4)}`, "Cost"]} cursor={{ fill: "rgba(255,255,255,0.02)" }} />
                  <Bar dataKey="cost" fill="rgba(251,191,36,0.6)" radius={[0,3,3,0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>

          <Card className="p-6">
            <h3 className="font-display font-semibold text-sm mb-4 flex items-center gap-2">
              <Zap className="w-4 h-4 text-secondary" /> Activity Timeline (Today)
            </h3>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={activityData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="time" tick={{ fill: "#888", fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis yAxisId="tasks" tick={{ fill: "#888", fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis yAxisId="tokens" orientation="right" tick={{ fill: "#888", fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line yAxisId="tasks" type="monotone" dataKey="tasks" stroke="rgba(0,240,255,0.8)" strokeWidth={2} dot={{ fill: "rgba(0,240,255,0.8)", r: 3 }} name="Tasks" />
                <Line yAxisId="tokens" type="monotone" dataKey="tokens" stroke="rgba(139,92,246,0.8)" strokeWidth={2} dot={{ fill: "rgba(139,92,246,0.8)", r: 3 }} name="Tokens" />
              </LineChart>
            </ResponsiveContainer>
          </Card>

          <Card className="p-6">
            <h3 className="font-display font-semibold text-sm mb-4">Recent Events</h3>
            <div className="space-y-3">
              {[
                { icon: CheckCircle, color: "text-emerald-400", msg: "Task 'Analyze competitor landscape' completed by Research Assistant", time: "2m ago" },
                { icon: Zap, color: "text-primary", msg: "AutoGPT loop iteration 4/10 — tool: tavily_search", time: "5m ago" },
                { icon: BarChart3, color: "text-secondary", msg: "Token budget 0.6% consumed — 74 tokens (gpt-4-turbo)", time: "5m ago" },
                { icon: AlertTriangle, color: "text-amber-400", msg: "ContextOverflow: Prompt exceeded 4096 tokens — chunking applied", time: "45m ago" },
                { icon: CheckCircle, color: "text-emerald-400", msg: "Short-term memory flushed — 48 entries archived to long-term", time: "2h ago" },
              ].map((ev: any, i: number) => (
                <div key={i} className="flex items-start gap-3 py-2 border-b border-white/5 last:border-0">
                  <ev.icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${ev.color}`} />
                  <div className="flex-1 text-sm text-foreground">{ev.msg}</div>
                  <div className="text-xs text-muted-foreground flex-shrink-0">{ev.time}</div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {activeTab === "tokens" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="p-6">
              <h3 className="font-display font-semibold text-sm mb-4">Input vs Output Tokens by Model</h3>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={tokenData} barGap={4}>
                  <XAxis dataKey="model" tick={{ fill: "#888", fontSize: 9 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fill: "#888", fontSize: 10 }} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(255,255,255,0.02)" }} />
                  <Bar dataKey="input" name="Input" fill="rgba(0,240,255,0.7)" radius={[3,3,0,0]} />
                  <Bar dataKey="output" name="Output" fill="rgba(139,92,246,0.7)" radius={[3,3,0,0]} />
                </BarChart>
              </ResponsiveContainer>
              <div className="flex gap-4 mt-2 justify-center text-xs text-muted-foreground">
                <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-primary/60" /> Input</span>
                <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-secondary/60" /> Output</span>
              </div>
            </Card>
            <Card className="p-6">
              <h3 className="font-display font-semibold text-sm mb-4">Agent Type Performance Radar</h3>
              <ResponsiveContainer width="100%" height={240}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="rgba(255,255,255,0.05)" />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: "#aaa", fontSize: 11 }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: "#666", fontSize: 9 }} />
                  <Radar name="Score" dataKey="A" stroke="rgba(0,240,255,0.8)" fill="rgba(0,240,255,0.15)" strokeWidth={2} />
                  <Tooltip contentStyle={tooltipStyle} />
                </RadarChart>
              </ResponsiveContainer>
            </Card>
          </div>
          <Card className="p-6">
            <h3 className="font-display font-semibold text-sm mb-4">Tool Usage (Tool Intelligence)</h3>
            <div className="space-y-3">
              {toolUsageData.map((t: any) => (
                <div key={t.tool} className="flex items-center gap-4">
                  <code className="text-xs text-muted-foreground w-32 flex-shrink-0">{t.tool}</code>
                  <div className="flex-1 bg-white/5 rounded-full h-2 overflow-hidden">
                    <div className="bg-primary/70 h-full rounded-full transition-all" style={{ width: `${(t.uses / 34) * 100}%` }} />
                  </div>
                  <span className="text-xs text-muted-foreground w-10 text-right">{t.uses}x</span>
                  <span className={cn("text-xs w-12 text-right font-mono", t.success >= 90 ? "text-emerald-400" : "text-amber-400")}>{t.success}%</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {activeTab === "self-improve" && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <KpiCard icon={RefreshCw} color="text-primary" label="Total Runs" value={totalRuns} sub="all agents" />
            <KpiCard icon={TrendingUp} color="text-emerald-400" label="Success Rate" value={successRate} sub="improving" />
            <KpiCard icon={Clock} color="text-amber-400" label="Avg Run Time" value={avgTime} sub="dynamic" />
            <KpiCard icon={AlertTriangle} color="text-red-400" label="Failures" value={stats?.failedTasks || 0} sub="analyzed" />
          </div>

          <Card className="p-6">
            <h3 className="font-display font-semibold text-sm mb-4 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-secondary" /> Self-Improvement Progress (v9 SelfImprovementEngine)
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={selfImproveTrend}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="run" tick={{ fill: "#888", fontSize: 11 }} tickLine={false} axisLine={false} label={{ value: "Run #", position: "insideBottom", fill: "#666", dy: 10 }} />
                <YAxis tick={{ fill: "#888", fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line type="monotone" dataKey="success" stroke="rgba(52,211,153,0.8)" strokeWidth={2} dot={{ r: 3 }} name="Success %" />
                <Line type="monotone" dataKey="time" stroke="rgba(251,191,36,0.8)" strokeWidth={2} dot={{ r: 3 }} name="Avg Time (s)" />
              </LineChart>
            </ResponsiveContainer>
          </Card>

          <Card className="p-6">
            <h3 className="font-display font-semibold text-sm mb-4 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400" /> Failure Analysis (FailureAnalyzer)
            </h3>
            <div className="space-y-4">
              {FAILURE_LOGS.map((f: any, i: number) => (
                <div key={i} className="p-4 rounded-xl bg-red-400/5 border border-red-400/10">
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-sm font-semibold text-red-400 font-mono">{f.type}</span>
                    <span className={cn("text-xs px-2 py-0.5 rounded-full",
                      f.severity >= 3 ? "bg-red-400/20 text-red-400" : "bg-amber-400/20 text-amber-400")}>
                      Severity {f.severity}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground mb-2">{f.cause}</p>
                  <div className="flex flex-wrap gap-2">
                    {f.recs.map((r: any, j: number) => (
                      <span key={j} className="text-xs px-2.5 py-1 rounded-full bg-white/5 border border-white/5 text-muted-foreground">
                        ↳ {r}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="p-6">
              <h3 className="font-display font-semibold text-sm mb-4 flex items-center gap-2">
                <Brain className="w-4 h-4 text-secondary" /> Prompt Optimizer
              </h3>
              <div className="space-y-3 text-sm">
                {[
                  { agent: "ResearchAgent", score: 87, change: "+12%" },
                  { agent: "CodingAgent", score: 74, change: "+8%" },
                  { agent: "WriterAgent", score: 91, change: "+5%" },
                ].map((p: any) => (
                  <div key={p.agent} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
                    <span className="font-mono text-muted-foreground">{p.agent}</span>
                    <div className="flex items-center gap-3">
                      <div className="w-24 bg-white/5 rounded-full h-1.5 overflow-hidden">
                        <div className="bg-secondary/70 h-full rounded-full" style={{ width: `${p.score}%` }} />
                      </div>
                      <span className="text-xs text-emerald-400 font-mono w-10">{p.change}</span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
            <Card className="p-6">
              <h3 className="font-display font-semibold text-sm mb-4 flex items-center gap-2">
                <Wrench className="w-4 h-4 text-amber-400" /> Tool Learning
              </h3>
              <div className="space-y-3 text-sm">
                {[
                  { tool: "tavily_search", score: 94, label: "High accuracy" },
                  { tool: "python_executor", score: 87, label: "Improving" },
                  { tool: "slack_tools", score: 75, label: "Needs tuning" },
                ].map((t: any) => (
                  <div key={t.tool} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
                    <div>
                      <div className="font-mono text-muted-foreground text-xs">{t.tool}</div>
                      <div className="text-xs text-muted-foreground/60">{t.label}</div>
                    </div>
                    <span className={cn("text-sm font-mono font-bold",
                      t.score >= 90 ? "text-emerald-400" : t.score >= 80 ? "text-amber-400" : "text-red-400")}>
                      {t.score}%
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}

      {activeTab === "tasks" && (
        <div className="space-y-6">
          <div className="grid grid-cols-3 gap-4">
            <KpiCard icon={Clock} color="text-amber-400" label="Queued" value={pendingTasks} sub="pending" />
            <KpiCard icon={Zap} color="text-primary" label="Running" value="0" sub="workers: auto" />
            <KpiCard icon={CheckCircle} color="text-emerald-400" label="Done" value={completedTasks} sub="this session" />
          </div>
          <Card className="p-6">
            <h3 className="font-display font-semibold text-sm mb-4 flex items-center gap-2">
              <Clock className="w-4 h-4 text-amber-400" /> Task Queue (QueueManager · WorkerPool)
            </h3>
            <div className="space-y-2">
              {[
                { id: "a1b2c3", name: "Competitor Analysis", status: "running", agent: "ResearchAgent", elapsed: "12s" },
                { id: "d4e5f6", name: "Blog Post Draft", status: "pending", agent: "WriterAgent", elapsed: "—" },
                { id: "g7h8i9", name: "Code Review PR #42", status: "pending", agent: "CodingAgent", elapsed: "—" },
                { id: "j0k1l2", name: "Summarize Slack Thread", status: "pending", agent: "CriticAgent", elapsed: "—" },
                { id: "m3n4o5", name: "Validate Dataset Schema", status: "completed", agent: "ValidatorAgent", elapsed: "8s" },
                { id: "p6q7r8", name: "Write README.md", status: "completed", agent: "WriterAgent", elapsed: "14s" },
              ].map((t: any) => (
                <div key={t.id} className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/5">
                  <div className="flex items-center gap-3">
                    <code className="text-xs text-muted-foreground/50 font-mono w-14 flex-shrink-0">{t.id}</code>
                    <div>
                      <div className="text-sm font-medium text-foreground">{t.name}</div>
                      <div className="text-xs text-muted-foreground">{t.agent}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-muted-foreground">{t.elapsed}</span>
                    <span className={cn("text-xs px-2 py-1 rounded-full font-medium",
                      t.status === "running" ? "bg-primary/20 text-primary" :
                      t.status === "completed" ? "bg-emerald-400/20 text-emerald-400" :
                      "bg-white/10 text-muted-foreground")}>
                      {t.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {activeTab === "builder" && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCard icon={CheckCircle} color="text-emerald-400" label="Build Success Rate" value="92.4%" sub="avg all time" />
            <KpiCard icon={RefreshCw} color="text-amber-400" label="Version Rollbacks" value="48" sub="this month" />
            <KpiCard icon={Zap} color="text-primary" label="Avg Fix Attempts" value="1.2" sub="per active build" />
            <KpiCard icon={DollarSign} color="text-secondary" label="Vercel Deployments" value="15" sub="successful" />
          </div>

          <Card className="p-6">
            <h3 className="font-display font-semibold text-sm mb-4 flex items-center gap-2">
              <Wrench className="w-4 h-4 text-emerald-400" /> Autonomous Builder Telemetry (Global)
            </h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center text-sm border-b border-white/10 pb-2">
                <span className="text-muted-foreground">Successful Updates (Patches)</span>
                <span className="font-mono text-emerald-400 font-bold">1,204</span>
              </div>
              <div className="flex justify-between items-center text-sm border-b border-white/10 pb-2">
                <span className="text-muted-foreground">Failed Updates (Revert/Retry)</span>
                <span className="font-mono text-red-400 font-bold">98</span>
              </div>
              <div className="flex justify-between items-center text-sm border-b border-white/10 pb-2">
                <span className="text-muted-foreground">Multi-Agent Pipeline Loops (Avg)</span>
                <span className="font-mono text-primary font-bold">1.2x</span>
              </div>
              <div className="flex justify-between items-center text-sm pb-2">
                <span className="text-muted-foreground">Vercel V13 API Integrations</span>
                <span className="font-mono text-cyan-400 font-bold">Active</span>
              </div>
            </div>
          </Card>
        </div>
      )}
    </Layout>
  );
}

function KpiCard({ icon: Icon, color, label, value, sub }: any) {
  return (
    <Card className="p-5 relative overflow-hidden">
      <div className="p-2 rounded-lg bg-white/5 w-fit mb-3"><Icon className={`w-5 h-5 ${color}`} /></div>
      <div className="text-2xl font-display font-bold text-foreground">{value}</div>
      <div className="text-xs text-muted-foreground mt-0.5">{label} <span className="opacity-60">({sub})</span></div>
      <div className={`absolute -bottom-5 -right-5 w-16 h-16 rounded-full blur-xl opacity-10 ${color.replace("text-", "bg-")}`} />
    </Card>
  );
}
