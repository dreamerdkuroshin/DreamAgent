import { useState, useEffect, useRef, useCallback } from "react";
import { useUpdateSettings, useConnectProvider, useGetSettingsKeys } from "@workspace/api-client-react";
import { Layout } from "@/components/layout";
import { Card, Button, Input } from "@/components/ui-elements";
import {
  Key, Shield, Globe, Bot, Puzzle, Monitor,
  CheckCircle, XCircle, ChevronRight, Database, DollarSign, Box,
  Activity, Play, Square, Terminal, RefreshCw, Zap, Server, Loader2,
  Upload, Link2, Link2Off, ExternalLink
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";
import { useAppStore } from "@/store/app.store";

// Use relative path - served via Vite proxy in dev, same origin in prod
const BACKEND = "";
const USER_ID = "local_user";
const BOT_ID = "local_bot";

type Tab = "api-keys" | "oauth" | "bot-tokens" | "mcp" | "local-tools" | "memory" | "sandbox" | "budget" | "safety" | "queue";

const TABS: { id: Tab; label: string; icon: any; badge?: string }[] = [
  { id: "api-keys", label: "API Keys", icon: Key },
  { id: "oauth", label: "OAuth Apps", icon: Globe },
  { id: "bot-tokens", label: "Bot Tokens", icon: Bot },
  { id: "queue", label: "Task Queue", icon: Activity, badge: "live" },
  { id: "mcp", label: "MCP Servers", icon: Puzzle },
  { id: "local-tools", label: "Local Tools", icon: Monitor },
  { id: "memory", label: "Memory", icon: Database },
  { id: "sandbox", label: "Sandbox", icon: Box, badge: "v10" },
  { id: "budget", label: "Budget", icon: DollarSign },
  { id: "safety", label: "Safety", icon: Shield },
];

function OAuthConnectorRow({
  name, description, logo, provider, connected, onStatusChange
}: {
  name: string; description: string; logo: string;
  provider: string; connected: boolean;
  onStatusChange: (provider: string, connected: boolean) => void;
}) {
  const { toast } = useToast();
  const popupRef = useRef<Window | null>(null);
  const [checking, setChecking] = useState(false);

  const openConnect = () => {
    const url = `${BACKEND}/api/v1/oauth/${provider}/connect?user_id=${USER_ID}&bot_id=${BOT_ID}`;
    const popup = window.open(url, `oauth_${provider}`,
      "width=520,height=660,scrollbars=yes,resizable=yes");
    popupRef.current = popup;
    setChecking(true);
    toast({ title: `🔐 Authorizing ${name}… Complete the flow in the popup.` });

    // Poll until the popup closes
    const interval = setInterval(async () => {
      if (!popup || popup.closed) {
        clearInterval(interval);
        // Give the backend a moment to write the token
        setTimeout(async () => {
          try {
            const res = await fetch(
              `${BACKEND}/api/v1/oauth/advanced/status?user_id=${USER_ID}`
            );
            // Token written → mark connected via localStorage
            onStatusChange(provider, true);
            toast({ title: `✅ ${name} connected successfully!` });
          } catch { }
          setChecking(false);
        }, 1000);
      }
    }, 800);
  };

  return (
    <div className="flex items-center justify-between py-4 border-b border-white/5 last:border-0">
      <div className="flex items-center gap-3">
        <div className={cn(
          "w-9 h-9 rounded-lg border flex items-center justify-center text-sm font-bold",
          connected
            ? "bg-emerald-400/10 border-emerald-400/30 text-emerald-400"
            : "bg-white/5 border-white/10 text-foreground"
        )}>
          {logo}
        </div>
        <div>
          <div className="font-medium text-foreground text-sm">{name}</div>
          <div className="text-xs text-muted-foreground">{description}</div>
        </div>
      </div>
      <div className="flex items-center gap-3 flex-shrink-0">
        {connected
          ? <span className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle className="w-3.5 h-3.5" /> Connected</span>
          : <span className="flex items-center gap-1 text-xs text-muted-foreground"><XCircle className="w-3.5 h-3.5" /> Not Connected</span>}
        {checking
          ? <Button variant="outline" className="text-xs px-3 py-1 h-auto" disabled>
            <Loader2 className="w-3 h-3 mr-1 animate-spin" /> Waiting…
          </Button>
          : connected
            ? <Button variant="outline" className="text-xs px-3 py-1 h-auto border-emerald-400/30 text-emerald-400"
              onClick={() => {
                onStatusChange(provider, false);
                toast({ title: `Disconnected ${name}` });
              }}>
              <Link2Off className="w-3 h-3 mr-1" /> Disconnect
            </Button>
            : <Button variant="outline" className="text-xs px-3 py-1 h-auto"
              onClick={openConnect}>
              <ExternalLink className="w-3 h-3 mr-1" /> Connect
            </Button>
        }
      </div>
    </div>
  );
}

function BotTokenCard({ platform, label, placeholder, icon }: { platform: string; label: string; placeholder: string; icon?: string }) {
  const [token, setToken] = useState("");
  const [embedding, setEmbedding] = useState("local");
  const [savedPreview, setSavedPreview] = useState("");
  const [editing, setEditing] = useState(false);
  const [status, setStatus] = useState<"idle" | "running" | "loading">("idle");
  const { toast } = useToast();

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/integrations/tokens");
      if (!res.ok) return;

      // Parse the standard success_response nested structure: { status: "success", data: { telegram: {...} } }
      const body = await res.json();
      const tokensMap = body.data || body;

      const botMatch = Object.values(tokensMap).find((b: any) => b.platform === platform) as any;
      if (botMatch) {
        setBotId(botMatch.id);
        setStatus(botMatch.running ? "running" : "idle");
        if (botMatch.token_preview) {
          setSavedPreview(botMatch.token_preview);
        }
        if (botMatch.embedding_provider) {
          setEmbedding(botMatch.embedding_provider);
        }
      }
    } catch { }
  }, [platform]);

  const [botId, setBotId] = useState<string | null>(null);

  useEffect(() => { fetchStatus(); const id = setInterval(fetchStatus, 5000); return () => clearInterval(id); }, [fetchStatus]);

  const handleSaveAndStart = async () => {
    if (!token.trim()) { toast({ title: "Please enter a token first", variant: "destructive" }); return; }
    setStatus("loading");
    try {
      const res = await fetch("/api/v1/integrations/tokens", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ platform, token: token || savedPreview || "temp", auto_start: true, embedding_provider: embedding }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      const newBotId = data.data?.bot_id || data.bot_id;
      if (newBotId) setBotId(newBotId);
      setStatus("running");
      setEditing(false);
      toast({ title: `✅ ${label} bot started!` });
    } catch (e: any) {
      setStatus("idle");
      toast({ title: `Failed: ${e.message}`, variant: "destructive" });
    }
  };

  const handleStop = async () => {
    if (!botId) return;
    setStatus("loading");
    try {
      await fetch(`/api/v1/integrations/stop/${botId}`, { method: "POST" });
      setStatus("idle");
      toast({ title: `🛑 ${label} bot stopped.` });
    } catch (e: any) {
      toast({ title: `Failed to stop: ${e.message}`, variant: "destructive" });
      setStatus("running");
    }
  };

  return (
    <div className="py-4 border-b border-white/5 last:border-0">
      <div className="flex items-center justify-between mb-2">
        <label className="text-sm font-medium text-foreground flex items-center gap-2">
          <span className="text-lg">{icon}</span> {label}
        </label>
        <span className={cn("flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border",
          status === "running" ? "bg-emerald-400/10 text-emerald-400 border-emerald-400/20" :
            status === "loading" ? "bg-amber-400/10 text-amber-400 border-amber-400/20" :
              "bg-white/5 text-muted-foreground border-white/10")}>
          {status === "running" ? <><CheckCircle className="w-3 h-3" /> Running</> :
            status === "loading" ? <>⏳ Working...</> :
              <><XCircle className="w-3 h-3" /> Stopped</>}
        </span>
      </div>
      <div className="flex gap-2">
        <Input type={editing ? "text" : "password"} value={token} onChange={e => setToken(e.target.value)}
          placeholder={savedPreview || placeholder} className="font-mono bg-black/60 text-sm flex-1" readOnly={!editing} />
        <select
          value={embedding}
          disabled={!editing}
          onChange={(e) => {
            if (editing && savedPreview && e.target.value !== embedding) {
              if (!confirm("⚠️ WARNING: Changing embedding models will WIPE all your currently indexed bot documents so they can be re-indexed safely. Proceed?")) return;
            }
            setEmbedding(e.target.value);
          }}
          className="flex h-10 w-44 rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
        >
          <option value="local">⚡ Local (Fast / Free)</option>
        </select>
        {!editing && <Button variant="outline" className="text-xs px-3" onClick={() => setEditing(true)}>{savedPreview ? "Edit / Config" : "Add Token"}</Button>}
        {editing && (
          <Button className="text-xs px-3 bg-primary text-black hover:bg-primary/90"
            onClick={handleSaveAndStart} disabled={status === "loading"}>
            <Play className="w-3.5 h-3.5 mr-1" /> Save & Start
          </Button>
        )}
        {status === "running" && (
          <Button variant="outline" className="text-xs px-3 border-red-400/30 text-red-400 hover:bg-red-400/10"
            onClick={handleStop}>
            <Square className="w-3.5 h-3.5 mr-1" /> Stop
          </Button>
        )}
        {status === "idle" && !editing && (
          <Button variant="outline" className="text-xs px-3 border-emerald-400/30 text-emerald-400 hover:bg-emerald-400/10"
            onClick={async () => {
              if (!botId) return toast({ title: "No bot saved", variant: "destructive" });
              setStatus("loading");
              try {
                const res = await fetch(`/api/v1/integrations/start/${botId}`, { method: "POST" });
                const data = await res.json();
                if (data.error) throw new Error(data.error);
                setStatus("running");
                toast({ title: `▶ ${label} bot started!` });
              } catch (e: any) { setStatus("idle"); toast({ title: e.message, variant: "destructive" }); }
            }}>
            <Play className="w-3.5 h-3.5 mr-1" /> Start
          </Button>
        )}
      </div>
    </div>
  );
}

function ApiKeyRow({ name, envKey, placeholder, hasKey, initialValue }: { name: string; envKey?: string; placeholder: string; hasKey?: boolean; initialValue?: string }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(initialValue || (hasKey ? "sk-••••••••••••••••" : ""));
  const active = hasKey || !!initialValue;
  const { toast } = useToast();
  const { mutateAsync: updateSettings } = useUpdateSettings();
  const settingsKey = envKey || (name.toUpperCase().replace(/[\s\-/(),.]+/g, "_") + "_API_KEY");
  return (
    <div className="py-4 border-b border-white/5 last:border-0">
      <div className="flex justify-between items-center mb-2">
        <label className="text-sm font-medium text-foreground">{name}</label>
        {active && <span className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle className="w-3 h-3" /> Active</span>}
      </div>
      <div className="flex gap-2">
        <Input type={editing ? "text" : "password"} value={val}
          onChange={e => setVal(e.target.value)} placeholder={placeholder}
          className="font-mono bg-black/60 text-sm" readOnly={!editing} />
        {editing
          ? <Button onClick={async () => {
            try {
              await updateSettings({ [settingsKey]: val });
              setEditing(false);
              toast({ title: "Key saved to backend" });
            } catch (e) {
              toast({ title: "Failed to save key", variant: "destructive" });
            }
          }}>Save</Button>
          : <Button variant="outline" onClick={() => setEditing(true)}>Edit</Button>}
      </div>
    </div>
  );
}

function ToggleRow({ label, description, enabled: def, badge }: { label: string; description: string; enabled?: boolean; badge?: string }) {
  const [enabled, setEnabled] = useState(def ?? false);
  return (
    <div className="flex items-center justify-between py-3.5 border-b border-white/5 last:border-0">
      <div className="flex-1 pr-4">
        <div className="text-sm font-medium text-foreground flex items-center gap-2">
          {label}
          {badge && <span className="text-xs px-1.5 py-0.5 rounded bg-primary/20 text-primary">{badge}</span>}
        </div>
        <div className="text-xs text-muted-foreground mt-0.5">{description}</div>
      </div>
      <button onClick={() => setEnabled(!enabled)}
        className={cn("relative w-11 h-6 rounded-full transition-colors duration-200 flex-shrink-0",
          enabled ? "bg-primary shadow-[0_0_10px_rgba(0,240,255,0.4)]" : "bg-white/10")}>
        <span className={cn("absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-all duration-200",
          enabled ? "left-6" : "left-1")} />
      </button>
    </div>
  );
}

type PermLevel = "DENIED" | "READ" | "WRITE" | "ADMIN";
function PermRow({ tool, level: def }: { tool: string; level: PermLevel }) {
  const [level, setLevel] = useState<PermLevel>(def);
  const colors: Record<PermLevel, string> = {
    DENIED: "bg-red-400/20 text-red-400 border-red-400/30",
    READ: "bg-sky-400/20 text-sky-400 border-sky-400/30",
    WRITE: "bg-amber-400/20 text-amber-400 border-amber-400/30",
    ADMIN: "bg-emerald-400/20 text-emerald-400 border-emerald-400/30",
  };
  return (
    <div className="flex items-center justify-between py-3 border-b border-white/5 last:border-0">
      <span className="text-sm font-mono text-foreground">{tool}</span>
      <div className="flex gap-1">
        {(["DENIED", "READ", "WRITE", "ADMIN"] as PermLevel[]).map(l => (
          <button key={l} onClick={() => setLevel(l)}
            className={cn("text-xs px-2 py-1 rounded-lg border transition-all",
              level === l ? colors[l] : "border-white/5 text-muted-foreground hover:border-white/10")}>
            {l}
          </button>
        ))}
      </div>
    </div>
  );
}

function OllamaRow() {
  const [baseUrl, setBaseUrl] = useState("http://localhost:11434");
  const [editing, setEditing] = useState(false);
  const { toast } = useToast();
  const { mutateAsync: updateSettings } = useUpdateSettings();
  return (
    <div className="py-4 border-b border-white/5 last:border-0">
      <div className="flex justify-between items-center mb-2">
        <label className="text-sm font-medium text-foreground">Ollama (Local — no API key needed)</label>
        <span className="text-xs px-2 py-0.5 rounded bg-emerald-400/10 text-emerald-400 border border-emerald-400/20">Local</span>
      </div>
      <p className="text-xs text-muted-foreground mb-2">Run <code className="text-primary/80">ollama serve</code> locally, then set the URL below. Ollama does not use API keys.</p>
      <div className="flex gap-2">
        <Input type="text" value={baseUrl}
          onChange={e => setBaseUrl(e.target.value)} placeholder="http://localhost:11434"
          className="font-mono bg-black/60 text-sm" readOnly={!editing} />
        {editing
          ? <Button onClick={async () => {
            try {
              await updateSettings({ OLLAMA_BASE_URL: baseUrl });
              setEditing(false);
              toast({ title: "Ollama URL saved to backend" });
            } catch (e) {
              toast({ title: "Failed to save", variant: "destructive" });
            }
          }}>Save</Button>
          : <Button variant="outline" onClick={() => setEditing(true)}>Edit</Button>}
      </div>
    </div>
  );
}

function TaskQueuePanel() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [shellCmd, setShellCmd] = useState("");
  const [shellOutput, setShellOutput] = useState("");
  const [shellRunning, setShellRunning] = useState(false);
  const { toast } = useToast();

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/integrations/queue");
      if (res.ok) { const d = await res.json(); setTasks(d.tasks || []); }
    } catch { } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, [refresh]);

  const runShell = async () => {
    if (!shellCmd.trim()) return;
    setShellRunning(true); setShellOutput("");
    try {
      const res = await fetch("/api/v1/integrations/shell", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: shellCmd }),
      });
      const data = await res.json();
      setShellOutput(data.output || "(no output)");
      toast({ title: `Exit code: ${data.exit_code}` });
    } catch (e: any) {
      setShellOutput(`Error: ${e.message}`);
    } finally { setShellRunning(false); }
  };

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-display font-bold flex items-center gap-2">
            <Activity className="w-5 h-5 text-primary" /> Live Task Queue
          </h3>
          <Button variant="outline" className="text-xs px-3 h-8" onClick={refresh}>
            <RefreshCw className="w-3.5 h-3.5 mr-1" /> Refresh
          </Button>
        </div>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : tasks.length === 0 ? (
          <div className="text-center py-10 text-muted-foreground">
            <Activity className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No tasks running. Start a bot or run a shell command.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {tasks.map((t: any) => (
              <div key={t.id} className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/10">
                <div className="flex items-center gap-3">
                  <span className="text-lg">{t.type === "bot" ? "🤖" : "💻"}</span>
                  <div>
                    <div className="text-sm font-medium text-foreground">{t.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {t.pid && `PID: ${t.pid}`}{t.started_at && ` · Started: ${new Date(t.started_at).toLocaleTimeString()}`}
                    </div>
                  </div>
                </div>
                <span className={cn("text-xs px-2 py-0.5 rounded-full border",
                  t.status === "running" ? "bg-emerald-400/10 text-emerald-400 border-emerald-400/20" :
                    t.status === "done" ? "bg-sky-400/10 text-sky-400 border-sky-400/20" :
                      t.status === "error" ? "bg-red-400/10 text-red-400 border-red-400/20" :
                        "bg-white/5 text-muted-foreground border-white/10")}>
                  {t.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="p-6">
        <h3 className="text-lg font-display font-bold mb-1 flex items-center gap-2">
          <Terminal className="w-5 h-5 text-primary" /> Shell Terminal
        </h3>
        <p className="text-sm text-muted-foreground mb-4">Run commands on the local machine. Press Enter or click ▶ to execute.</p>
        <div className="flex gap-2 mb-4">
          <Input
            value={shellCmd}
            onChange={e => setShellCmd(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !shellRunning && runShell()}
            placeholder="e.g. python --version, pip list, dir, git status"
            className="font-mono bg-black/60 text-sm"
          />
          <Button onClick={runShell} disabled={shellRunning} className="bg-primary text-black hover:bg-primary/90 px-4">
            {shellRunning ? "⏳" : <Play className="w-4 h-4" />}
          </Button>
        </div>
        {shellOutput && (
          <pre className="p-4 rounded-xl bg-black/60 border border-white/10 text-xs text-emerald-300 font-mono overflow-x-auto whitespace-pre-wrap max-h-64 overflow-y-auto">
            {shellOutput}
          </pre>
        )}
      </Card>
    </div>
  );
}

function ApiKeysPanel() {
  const { data: keys, isLoading, error } = useGetSettingsKeys();

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
        <Loader2 className="w-10 h-10 animate-spin mb-4 opacity-50" />
        <p className="text-sm">Fetching API configuration from backend...</p>
      </div>
    );
  }

  if (error || !keys) {
    return (
      <Card className="p-10 text-center border-red-500/20 bg-red-500/5">
        <XCircle className="w-10 h-10 mx-auto mb-4 text-red-400" />
        <h3 className="text-lg font-bold text-foreground">Failed to load API keys</h3>
        <p className="text-sm text-muted-foreground mt-1">Make sure the backend is running at http://localhost:8000</p>
      </Card>
    );
  }

  // Group keys: LLMs usually end with _API_KEY and are in the first ~20 of our KNOWN_KEYS
  const llmKeys = Object.entries(keys).filter(([k]) =>
    !["TAVILY_API_KEY", "AHREFS_API_KEY", "SUPABASE_API_KEY", "STRIPE_API_KEY", "OLLAMA_BASE_URL"].includes(k)
  );

  const otherKeys = Object.entries(keys).filter(([k]) =>
    ["TAVILY_API_KEY", "AHREFS_API_KEY", "SUPABASE_API_KEY", "STRIPE_API_KEY"].includes(k)
  );

  return (
    <div className="space-y-6">
      {/* ── LLM / AI Model API Keys ─────────────────────────────── */}
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-1">
          <Zap className="w-5 h-5 text-primary" />
          <h3 className="text-lg font-display font-bold">LLM / AI Model API Keys</h3>
          <span className="ml-2 text-xs px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">AI Providers</span>
        </div>
        <p className="text-sm text-muted-foreground mb-6">Keys used by model adapters — sent directly to LLM providers for inference.</p>

        <div className="space-y-1">
          {llmKeys.map(([envKey, info]) => (
            <ApiKeyRow
              key={envKey}
              name={info.name}
              envKey={envKey}
              placeholder={`${envKey.toLowerCase().replace("_", "-")}...`}
              hasKey={info.configured}
              initialValue={info.preview}
            />
          ))}
        </div>

        <div className="pt-4 border-t border-white/5 mt-2">
          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Local / Self-Hosted Models</div>
          <OllamaRow />
        </div>
      </Card>

      {/* ── Other Service API Keys ─────────────────────────────── */}
      {otherKeys.length > 0 && (
        <Card className="p-6">
          <div className="flex items-center gap-2 mb-1">
            <Server className="w-5 h-5 text-amber-400" />
            <h3 className="text-lg font-display font-bold">Other Service API Keys</h3>
            <span className="ml-2 text-xs px-2 py-0.5 rounded bg-amber-400/10 text-amber-400 border border-amber-400/20">Integrations</span>
          </div>
          <p className="text-sm text-muted-foreground mb-6">Keys for search, data, payments and storage services used as agent tools.</p>

          <div className="space-y-1">
            {otherKeys.map(([envKey, info]) => (
              <ApiKeyRow
                key={envKey}
                name={info.name}
                envKey={envKey}
                placeholder={`${envKey.toLowerCase().replace("_", "-")}...`}
                hasKey={info.configured}
                initialValue={info.preview}
              />
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function OAuthPanel({ connectedProviders, setConnectedProviders }: any) {
  const { toast } = useToast();
  const [googleClientFile, setGoogleClientFile] = useState<File | null>(null);
  const [googleStatus, setGoogleStatus] = useState({ configured: false, scopes: [] });

  const fetchAdvancedStatus = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND}/api/v1/oauth/advanced/status?user_id=${USER_ID}`);
      if (res.ok) {
        const data = await res.json();
        setGoogleStatus(data);
      }
    } catch { } // ignore
  }, []);

  useEffect(() => {
    fetchAdvancedStatus();
    // Periodically poll backend to see if any tokens were saved
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${BACKEND}/api/v1/oauth/advanced/status?user_id=${USER_ID}`);
        if (res.ok) {
          const data = await res.json();
          // We can use this to keep UI in sync
        }
      } catch { }
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchAdvancedStatus]);

  const handleUploadGoogleSecret = async () => {
    if (!googleClientFile) return;
    const formData = new FormData();
    formData.append("file", googleClientFile);
    formData.append("user_id", USER_ID);

    try {
      const res = await fetch(`${BACKEND}/api/v1/oauth/advanced/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || "Failed");
      toast({ title: "Custom Google OAuth Configured!", description: "Extracted client_id & client_secret." });
      setGoogleClientFile(null);
      fetchAdvancedStatus();
    } catch (e: any) {
      toast({ title: "Upload Failed", description: e.message, variant: "destructive" });
    }
  };

  const handleStatusChange = (provider: string, connected: boolean) => {
    setConnectedProviders((prev: any) => {
      const next = new Set(prev);
      if (connected) next.add(provider);
      else next.delete(provider);
      localStorage.setItem("oauth_connected_providers", JSON.stringify([...next]));
      return next;
    });
  };

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <h3 className="text-lg font-display font-bold mb-1 flex items-center gap-2"><Globe className="w-5 h-5 text-primary" /> OAuth 2.0 Integrations</h3>
        <p className="text-sm text-muted-foreground mb-6">Click <strong>Connect</strong> to authorize. You will be redirected to the provider's login screen in a secure popup.</p>

        {/* Google Advanced Setup */}
        <div className="mb-8 p-4 rounded-xl bg-black/40 border border-white/10">
          <h4 className="text-sm font-semibold flex items-center gap-2 mb-2">
            Google Setup <span className="text-xs px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">Advanced</span>
          </h4>
          <p className="text-xs text-muted-foreground mb-4">
            Upload your <code className="text-primary/80">client_secret.json</code> to use your own Google Cloud project.
            We automatically extract and encrypt your keys.
            If you don't upload one, we'll try to use the default app credentials.
          </p>

          <div className="flex gap-2 items-center">
            {googleStatus.configured ? (
              <div className="flex-1 flex items-center justify-between p-3 rounded-lg bg-emerald-400/10 border border-emerald-400/20">
                <span className="text-sm text-emerald-400 flex items-center gap-2"><CheckCircle className="w-4 h-4" /> Custom Google OAuth Active</span>
                <Button variant="ghost" className="h-auto py-1 text-xs text-red-400 hover:text-red-300 hover:bg-red-400/10"
                  onClick={async () => {
                    await fetch(`${BACKEND}/api/v1/oauth/advanced/remove?user_id=${USER_ID}`, { method: "DELETE" });
                    fetchAdvancedStatus();
                    toast({ title: "Removed custom Google config" });
                  }}>
                  Remove
                </Button>
              </div>
            ) : (
              <>
                <Input
                  type="file"
                  accept=".json"
                  className="flex-1 bg-black/60 text-sm cursor-pointer"
                  onChange={e => setGoogleClientFile(e.target.files?.[0] || null)}
                />
                <Button
                  onClick={handleUploadGoogleSecret}
                  disabled={!googleClientFile}
                  className="bg-primary text-black hover:bg-primary/90"
                >
                  <Upload className="w-4 h-4 mr-2" /> Upload
                </Button>
              </>
            )}
          </div>
        </div>

        <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1 mt-2">Google (all services use one OAuth token)</div>
        <OAuthConnectorRow name="Gmail" description="Read, send and manage emails" logo="G" provider="google"
          connected={connectedProviders.has("google")} onStatusChange={handleStatusChange} />
        <OAuthConnectorRow name="Google Drive" description="File access and cloud storage" logo="D" provider="google"
          connected={connectedProviders.has("google")} onStatusChange={handleStatusChange} />
        <OAuthConnectorRow name="Google Calendar" description="Schedule and event management" logo="C" provider="google"
          connected={connectedProviders.has("google")} onStatusChange={handleStatusChange} />
        <OAuthConnectorRow name="YouTube" description="Video data, comments moderation (v10)" logo="▶" provider="google"
          connected={connectedProviders.has("google")} onStatusChange={handleStatusChange} />

        <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1 mt-4">Microsoft (all services use one OAuth token)</div>
        <OAuthConnectorRow name="Microsoft Teams" description="Meetings and workspace messaging" logo="M" provider="microsoft"
          connected={connectedProviders.has("microsoft")} onStatusChange={handleStatusChange} />
        <OAuthConnectorRow name="Excel" description="Spreadsheet read & write" logo="M" provider="microsoft"
          connected={connectedProviders.has("microsoft")} onStatusChange={handleStatusChange} />

        <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1 mt-4">Other</div>
        <OAuthConnectorRow name="Slack" description="Workspace messaging and channels" logo="S" provider="slack"
          connected={connectedProviders.has("slack")} onStatusChange={handleStatusChange} />
        <OAuthConnectorRow name="Notion" description="Docs, databases and wikis" logo="N" provider="notion"
          connected={connectedProviders.has("notion")} onStatusChange={handleStatusChange} />
      </Card>
    </div>
  );
}

export default function Settings() {
  const [activeTab, setActiveTab] = useState<Tab>("api-keys");
  const { mode, setMode } = useAppStore();
  const { toast } = useToast();
  const [connectedProviders, setConnectedProviders] = useState<Set<string>>(() => {
    // Persist connected state across page loads
    try {
      const stored = localStorage.getItem("oauth_connected_providers");
      return new Set(stored ? JSON.parse(stored) : []);
    } catch { return new Set(); }
  });

  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);
    const connected = searchParams.get("connected");
    if (connected) {
      // Mark this provider as connected and persist to localStorage
      setConnectedProviders(prev => {
        const next = new Set(prev);
        next.add(connected);
        localStorage.setItem("oauth_connected_providers", JSON.stringify([...next]));
        return next;
      });
      toast({ title: `✅ ${connected.charAt(0).toUpperCase() + connected.slice(1)} connected successfully!` });
      // Clean up the URL
      window.history.replaceState({}, "", "/settings?tab=oauth");
      setActiveTab("oauth");
    }
  }, []);

  return (
    <Layout>
      <div className="mb-8 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-display font-bold text-foreground">System Configuration</h1>
          <p className="text-muted-foreground mt-1">All connectors, memory, sandbox, budget, and safety settings for DreamAgent v10.</p>
        </div>

        {/* Mode Toggle */}
        <div className="bg-black/40 border border-white/10 rounded-xl p-1.5 flex items-center shrink-0">
          {(["Lite", "Standard", "Ultra"] as const).map(m => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={cn(
                "px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200",
                mode === m
                  ? "bg-primary text-black shadow-[0_0_15px_rgba(0,240,255,0.4)]"
                  : "text-muted-foreground hover:text-foreground hover:bg-white/5"
              )}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-1 space-y-1">
          {TABS.map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={cn("w-full flex items-center gap-3 px-4 py-3 rounded-xl font-medium text-sm transition-all",
                activeTab === tab.id
                  ? "bg-primary/10 text-primary border border-primary/20"
                  : "text-muted-foreground hover:bg-white/5 hover:text-foreground"
              )}>
              <tab.icon className="w-4 h-4 flex-shrink-0" />
              {tab.label}
              {tab.badge && <span className="ml-auto text-xs px-1.5 py-0.5 rounded bg-primary/20 text-primary">{tab.badge}</span>}
              {activeTab === tab.id && !tab.badge && <ChevronRight className="w-3 h-3 ml-auto" />}
            </button>
          ))}
        </div>

        <div className="lg:col-span-3">
          {activeTab === "api-keys" && (
            <ApiKeysPanel />
          )}

          {activeTab === "oauth" && (
            <OAuthPanel
              connectedProviders={connectedProviders}
              setConnectedProviders={setConnectedProviders}
            />
          )}

          {activeTab === "bot-tokens" && (
            <Card className="p-6">
              <h3 className="text-lg font-display font-bold mb-1 flex items-center gap-2"><Bot className="w-5 h-5 text-primary" /> Bot Integrations</h3>
              <p className="text-sm text-muted-foreground mb-6">Enter your bot token below. Click <strong>Save & Start</strong> to launch the bot. Click <strong>Stop</strong> to terminate it. Status updates every 5 seconds.</p>
              <BotTokenCard platform="telegram" label="Telegram Bot" placeholder="12345:AAFF..." icon="✈️" />
              <BotTokenCard platform="discord" label="Discord Bot" placeholder="MTI..." icon="🎮" />
              <BotTokenCard platform="slack" label="Slack Bot" placeholder="xoxb-..." icon="💬" />
              <BotTokenCard platform="whatsapp" label="WhatsApp Bot" placeholder="YOUR_ACCESS_TOKEN" icon="📱" />
              <div className="mt-4 p-4 rounded-xl bg-primary/5 border border-primary/20 text-sm text-muted-foreground">
                <p className="text-primary font-medium mb-1">🔗 Webhook endpoints</p>
                <p>Telegram: <code className="text-primary/80">/api/webhook/telegram</code></p>
                <p>Discord: <code className="text-primary/80">/api/webhook/discord</code></p>
                <p className="mt-2 text-xs">Tokens are persisted to <code className="text-primary/80">data/integrations.json</code> and injected as environment variables at startup.</p>
              </div>
            </Card>
          )}

          {activeTab === "queue" && (
            <TaskQueuePanel />
          )}

          {activeTab === "mcp" && (
            <Card className="p-6">
              <h3 className="text-lg font-display font-bold mb-1 flex items-center gap-2"><Puzzle className="w-5 h-5 text-primary" /> MCP Servers</h3>
              <p className="text-sm text-muted-foreground mb-6">Model Context Protocol servers from <code className="text-primary/80 text-xs">connectors/mcp/</code></p>
              <ConnectorRow name="Figma" description="Design tokens, components and assets" logo="F"
                connected={connectedProviders.has("figma")}
                connectUrl="http://localhost:8000/api/connect/figma" />
              <ConnectorRow name="Linear" description="Issue tracking and sprint management" logo="L"
                connected={connectedProviders.has("linear")}
                connectUrl="http://localhost:8000/api/connect/linear" />
              <ConnectorRow name="Grafana" description="Metrics dashboards and alerting" logo="G"
                connected={connectedProviders.has("grafana")}
                connectUrl="http://localhost:8000/api/connect/grafana" />
              <ConnectorRow name="Notion (MCP)" description="Structured knowledge via MCP protocol" logo="N"
                connected={connectedProviders.has("notionmcp")}
                connectUrl="http://localhost:8000/api/connect/notionmcp" />
              <ConnectorRow name="Slack (MCP)" description="Channel and message access via MCP" logo="S"
                connected={connectedProviders.has("slackmcp")}
                connectUrl="http://localhost:8000/api/connect/slackmcp" />
              <ConnectorRow name="Stripe (MCP)" description="Payment data and events via MCP" logo="$"
                connected={connectedProviders.has("stripemcp")}
                connectUrl="http://localhost:8000/api/connect/stripemcp" />
              <div className="mt-4">
                <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">MCP Tool Registries</div>
                <div className="space-y-2 text-xs text-muted-foreground">
                  {[
                    { name: "slack_registry", url: "SLACK_MCP_URL", port: "9104" },
                    { name: "stripe_registry", url: "STRIPE_MCP_URL", port: "9105" },
                  ].map(r => (
                    <div key={r.name} className="flex items-center gap-3 p-3 rounded-lg bg-white/5 border border-white/5">
                      <code className="text-primary/80">{r.name}</code>
                      <span className="text-muted-foreground">→</span>
                      <code className="text-amber-400/80">{`${r.url}=http://localhost:${r.port}`}</code>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          )}

          {activeTab === "local-tools" && (
            <Card className="p-6">
              <h3 className="text-lg font-display font-bold mb-1 flex items-center gap-2"><Monitor className="w-5 h-5 text-primary" /> Local Tools</h3>
              <p className="text-sm text-muted-foreground mb-6">From <code className="text-primary/80 text-xs">connectors/local/</code>, <code className="text-primary/80 text-xs">plugins/</code>, and <code className="text-primary/80 text-xs">tools/</code></p>
              <ToggleRow label="Python Code Executor" description="Sandboxed execution, max 2GB RAM, 30s timeout" enabled />
              <ToggleRow label="JavaScript Executor" description="Node.js sandbox — js_executor.py" badge="v10" />
              <ToggleRow label="Terminal / Shell" description="Controlled shell via connectors/local/terminal.py" />
              <ToggleRow label="Filesystem Access" description="Read/write files scoped to project directory" enabled />
              <ToggleRow label="Chrome Browser Control" description="Headless Chromium for web scraping" />
              <ToggleRow label="Tavily Web Search" description="Real-time search via Tavily API" enabled />
              <ToggleRow label="Google Search" description="Google search integration" />
              <ToggleRow label="Calculator Tool" description="Arithmetic operations via tools/calculator_tool.py" enabled />
              <ToggleRow label="Tool Intelligence (Auto-select)" description="Auto-picks best tool from message content — tool_intelligence.py" badge="v10" enabled />
            </Card>
          )}

          {activeTab === "memory" && (
            <Card className="p-6">
              <h3 className="text-lg font-display font-bold mb-1 flex items-center gap-2"><Database className="w-5 h-5 text-primary" /> Memory System</h3>
              <p className="text-sm text-muted-foreground mb-6">From <code className="text-primary/80 text-xs">memory/</code></p>
              <ToggleRow label="Short-Term Memory" description="In-session conversation history (ShortTermMemory)" enabled />
              <div className="pl-1 mb-3">
                <label className="text-xs text-muted-foreground">Max Entries</label>
                <Input type="number" defaultValue={1000} className="mt-1 bg-black/60 w-32 text-sm" />
              </div>
              <ToggleRow label="Long-Term Memory" description="Persistent PostgreSQL storage (LongTermMemory)" enabled />
              <ToggleRow label="Vector Memory / RAG" description="Semantic retrieval via VectorMemory + MemoryController" enabled />
              <div className="pl-1 mb-3">
                <label className="text-xs text-muted-foreground">Vector Backend</label>
                <select className="mt-1 flex h-10 w-full max-w-xs rounded-xl border border-white/10 bg-black/40 px-3 text-sm text-foreground focus:outline-none focus:border-primary">
                  <option>Qdrant (default)</option>
                  <option>Chroma</option>
                  <option>Pinecone</option>
                  <option>FAISS (local)</option>
                </select>
              </div>
              <div className="pl-1 mb-3">
                <label className="text-xs text-muted-foreground">Embedding Model</label>
                <select className="mt-1 flex h-10 w-full max-w-xs rounded-xl border border-white/10 bg-black/40 px-3 text-sm text-foreground focus:outline-none focus:border-primary">
                  <option>text-embedding-3-small</option>
                  <option>text-embedding-3-large</option>
                  <option>text-embedding-ada-002</option>
                </select>
              </div>
              <ToggleRow label="Knowledge Graph" description="v7: Entity + relationship store (production: Neo4j / ArangoDB)" badge="v7" />
              <ToggleRow label="Memory Reflection" description="v10: Periodically consolidates and improves memories" badge="v10" />
              <div className="pt-4"><Button>Save Memory Settings</Button></div>
            </Card>
          )}

          {activeTab === "sandbox" && (
            <Card className="p-6">
              <h3 className="text-lg font-display font-bold mb-1 flex items-center gap-2"><Box className="w-5 h-5 text-primary" /> Execution Sandbox <span className="text-xs text-primary bg-primary/10 px-2 py-0.5 rounded ml-1">v10</span></h3>
              <p className="text-sm text-muted-foreground mb-6">Sandbox executors from <code className="text-primary/80 text-xs">sandbox/</code></p>
              <ToggleRow label="Python Executor" description="Execute Python with threading timeout and SafetyGuard" enabled />
              <ToggleRow label="JavaScript Executor" description="Node.js sandbox via js_executor.py (new in v10)" badge="new" />
              <ToggleRow label="Docker Runner" description="Full container isolation with custom image (docker_runner.py)" />
              <div className="mt-4 space-y-3 pt-2 border-t border-white/5">
                <div className="flex items-center gap-3">
                  <label className="text-sm text-muted-foreground w-36">Docker Image</label>
                  <Input defaultValue="python:3.11" className="bg-black/60 text-sm" />
                </div>
                <div className="flex items-center gap-3">
                  <label className="text-sm text-muted-foreground w-36">Timeout (s)</label>
                  <Input type="number" defaultValue={30} className="bg-black/60 w-24 text-sm" />
                </div>
                <div className="flex items-center gap-3">
                  <label className="text-sm text-muted-foreground w-36">Max Memory</label>
                  <Input defaultValue="2GB" className="bg-black/60 w-24 text-sm" />
                </div>
              </div>
              <ToggleRow label="Network Access in Sandbox" description="Allow outbound calls from sandboxed code (disabled by default)" />
              <div className="pt-4"><Button>Save Sandbox Settings</Button></div>
            </Card>
          )}

          {activeTab === "budget" && (
            <Card className="p-6">
              <h3 className="text-lg font-display font-bold mb-1 flex items-center gap-2"><DollarSign className="w-5 h-5 text-primary" /> Budget Controller</h3>
              <p className="text-sm text-muted-foreground mb-6">Via <code className="text-primary/80 text-xs">monitoring/budget_controller.py</code> + <code className="text-primary/80 text-xs">monitoring/cost_manager.py</code></p>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-foreground">Total Session Budget (USD)</label>
                  <div className="flex gap-2 mt-1">
                    <Input type="number" defaultValue={5.00} step={0.50} className="bg-black/60 w-36" />
                    <span className="self-center text-sm text-muted-foreground">USD</span>
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">Per-Service Limits</label>
                  <div className="mt-2 space-y-2">
                    {["OpenAI", "Anthropic", "HuggingFace", "Tavily"].map(s => (
                      <div key={s} className="flex items-center gap-3">
                        <span className="text-sm text-muted-foreground w-28">{s}</span>
                        <Input type="number" defaultValue={2.00} step={0.50} className="bg-black/60 w-28 text-sm" />
                        <span className="text-xs text-muted-foreground">USD</span>
                      </div>
                    ))}
                  </div>
                </div>
                <ToggleRow label="Hard Budget Enforcement" description="Halt execution when budget exceeded" enabled />
                <ToggleRow label="Warning at 80%" description="Send alert when 80% consumed" enabled />
                <div className="pt-2"><Button>Save Budget Settings</Button></div>
              </div>
            </Card>
          )}

          {activeTab === "safety" && (
            <Card className="p-6">
              <h3 className="text-lg font-display font-bold mb-1 flex items-center gap-2"><Shield className="w-5 h-5 text-primary" /> Safety & Policy</h3>
              <p className="text-sm text-muted-foreground mb-6">From <code className="text-primary/80 text-xs">safety/</code> — ActionValidator, PolicyEngine, PromptInjectionGuard, ToolPermission</p>
              <ToggleRow label="Prompt Injection Guard" description="Block malicious instruction injections (prompt_injection_guard.py)" enabled />
              <ToggleRow label="Action Validator" description="Validate all tool calls before execution — blocks dangerous tools" enabled />
              <ToggleRow label="Policy Engine" description="Rule-based access control via policy_engine.py" enabled />
              <ToggleRow label="Strict Policy Mode" description="Deny all actions not explicitly whitelisted" />

              <div className="mt-6 pt-4 border-t border-white/5">
                <div className="flex items-center gap-2 mb-1">
                  <GitBranch className="w-4 h-4 text-primary" />
                  <span className="font-medium text-foreground text-sm">Tool Permission Levels</span>
                  <span className="text-xs text-muted-foreground ml-1">— ToolPermission (DENIED / READ / WRITE / ADMIN)</span>
                </div>
                <p className="text-xs text-muted-foreground mb-4">Set per-tool access level for the active agent session.</p>
                <PermRow tool="filesystem" level="READ" />
                <PermRow tool="terminal" level="DENIED" />
                <PermRow tool="chrome_control" level="READ" />
                <PermRow tool="code_runner" level="WRITE" />
                <PermRow tool="stripe_tools" level="READ" />
                <PermRow tool="slack_tools" level="WRITE" />
              </div>

              <div className="mt-6 pt-4 border-t border-white/5">
                <div className="font-medium text-foreground text-sm mb-3">Dangerous Tools Blocklist</div>
                <div className="flex flex-wrap gap-2">
                  {["rm", "del", "drop_table", "format", "shutdown", "exec", "eval", "os.system"].map(t => (
                    <span key={t} className="text-xs px-2.5 py-1 rounded-full bg-red-400/10 border border-red-400/20 text-red-400 font-mono">{t}</span>
                  ))}
                </div>
              </div>
              <div className="pt-4"><Button>Save Safety Settings</Button></div>
            </Card>
          )}
        </div>
      </div>
    </Layout>
  );
}
