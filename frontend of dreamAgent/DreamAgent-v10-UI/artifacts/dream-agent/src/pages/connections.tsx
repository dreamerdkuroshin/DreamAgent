import { useState, useEffect, useCallback } from "react";
import { Layout } from "@/components/layout";
import {
  Plug,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Download,
  Trash2,
  Wifi,
  WifiOff,
  ChevronRight,
  Package,
  Globe,
  Terminal,
  Sparkles,
  AlertTriangle,
} from "lucide-react";
import { useAppStore } from "@/store/app.store";

// ─────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────
interface MarketplaceTool {
  id: string;
  name: string;
  type: string;
  connection: string;
  description: string;
}

interface InstalledTool extends MarketplaceTool {
  tool_id: string;
  connected: boolean;
}

// ─────────────────────────────────────────────────────────
// Status Pill
// ─────────────────────────────────────────────────────────
function StatusBadge({ connected }: { connected: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
        connected
          ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
          : "bg-red-500/15 text-red-400 border border-red-500/30"
      }`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full animate-pulse ${
          connected ? "bg-emerald-400" : "bg-red-400"
        }`}
      />
      {connected ? "Connected" : "Disconnected"}
    </span>
  );
}

// ─────────────────────────────────────────────────────────
// Connection type icon
// ─────────────────────────────────────────────────────────
function ConnectionIcon({ type }: { type: string }) {
  if (type === "stdio") return <Terminal size={14} className="text-violet-400" />;
  if (type === "sse") return <Globe size={14} className="text-sky-400" />;
  return <Package size={14} className="text-slate-400" />;
}

// ─────────────────────────────────────────────────────────
// Installed Tool Card
// ─────────────────────────────────────────────────────────
function InstalledCard({
  tool,
  onReconnect,
  onUninstall,
  loading,
}: {
  tool: InstalledTool;
  onReconnect: (id: string) => void;
  onUninstall: (id: string) => void;
  loading: boolean;
}) {
  return (
    <div
      className={`relative group rounded-2xl border p-5 transition-all duration-300 backdrop-blur-sm ${
        tool.connected
          ? "border-emerald-500/20 bg-gradient-to-br from-slate-900 to-emerald-950/20 shadow-emerald-950/40"
          : "border-red-500/20 bg-gradient-to-br from-slate-900 to-red-950/20 shadow-red-950/40"
      } shadow-lg hover:scale-[1.01]`}
    >
      {/* Glow accent */}
      <div
        className={`absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none ${
          tool.connected
            ? "shadow-[inset_0_0_40px_rgba(16,185,129,0.05)]"
            : "shadow-[inset_0_0_40px_rgba(239,68,68,0.05)]"
        }`}
      />

      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          {/* Icon bubble */}
          <div
            className={`flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center ${
              tool.connected ? "bg-emerald-500/10" : "bg-red-500/10"
            }`}
          >
            {tool.connected ? (
              <Wifi size={18} className="text-emerald-400" />
            ) : (
              <WifiOff size={18} className="text-red-400" />
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-white text-sm">{tool.name}</span>
              <StatusBadge connected={tool.connected} />
            </div>
            <p className="text-slate-400 text-xs mt-1 leading-relaxed">{tool.description}</p>
            <div className="flex items-center gap-3 mt-2">
              <span className="flex items-center gap-1 text-xs text-slate-500">
                <ConnectionIcon type={tool.connection} />
                {tool.connection.toUpperCase()}
              </span>
              <span className="text-slate-600">·</span>
              <span className="text-xs text-slate-500 uppercase tracking-wide">{tool.type}</span>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-2 flex-shrink-0">
          {!tool.connected && (
            <button
              onClick={() => onReconnect(tool.tool_id)}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-medium transition-colors disabled:opacity-50"
            >
              <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
              Reconnect
            </button>
          )}
          <button
            onClick={() => onUninstall(tool.tool_id)}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-red-900/60 text-slate-400 hover:text-red-300 text-xs font-medium transition-colors disabled:opacity-50"
          >
            <Trash2 size={12} />
            Remove
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Marketplace Tool Card
// ─────────────────────────────────────────────────────────
function MarketplaceCard({
  tool,
  installed,
  onInstall,
  loading,
}: {
  tool: MarketplaceTool;
  installed: boolean;
  onInstall: (id: string) => void;
  loading: boolean;
}) {
  return (
    <div className="group rounded-2xl border border-slate-700/50 hover:border-violet-500/40 bg-gradient-to-br from-slate-900 to-slate-800/60 p-5 transition-all duration-300 hover:scale-[1.01] shadow-lg">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-violet-600/10 flex items-center justify-center">
            <Package size={18} className="text-violet-400" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-white text-sm">{tool.name}</span>
              {installed && (
                <span className="text-xs px-2 py-0.5 bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 rounded-full">
                  Installed
                </span>
              )}
            </div>
            <p className="text-slate-400 text-xs mt-1 leading-relaxed">{tool.description}</p>
            <div className="flex items-center gap-2 mt-2">
              <span className="flex items-center gap-1 text-xs text-slate-500">
                <ConnectionIcon type={tool.connection} />
                {tool.connection.toUpperCase()}
              </span>
            </div>
          </div>
        </div>

        <button
          onClick={() => !installed && onInstall(tool.id)}
          disabled={installed || loading}
          className={`flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            installed
              ? "bg-slate-800 text-slate-500 cursor-not-allowed"
              : "bg-violet-600 hover:bg-violet-500 text-white"
          } disabled:opacity-60`}
        >
          {installed ? (
            <CheckCircle2 size={12} />
          ) : loading ? (
            <RefreshCw size={12} className="animate-spin" />
          ) : (
            <Download size={12} />
          )}
          {installed ? "Installed" : "Install"}
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Summary Stats Bar
// ─────────────────────────────────────────────────────────
function StatsBar({
  total,
  connected,
  disconnected,
}: {
  total: number;
  connected: number;
  disconnected: number;
}) {
  return (
    <div className="grid grid-cols-3 gap-3">
      {[
        { label: "Installed", value: total, color: "text-slate-300", bg: "bg-slate-800/60" },
        { label: "Connected", value: connected, color: "text-emerald-400", bg: "bg-emerald-500/10" },
        { label: "Offline", value: disconnected, color: "text-red-400", bg: "bg-red-500/10" },
      ].map((s) => (
        <div
          key={s.label}
          className={`${s.bg} border border-slate-700/50 rounded-xl px-4 py-3 text-center`}
        >
          <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
          <div className="text-xs text-slate-500 mt-0.5">{s.label}</div>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────
export default function Connections() {
  const { activeBotId } = useAppStore();
  const userId = "1"; // TODO: pull from auth context
  const botId = activeBotId ?? "1";

  const [installed, setInstalled] = useState<InstalledTool[]>([]);
  const [marketplace, setMarketplace] = useState<MarketplaceTool[]>([]);
  const [fetching, setFetching] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [tab, setTab] = useState<"installed" | "marketplace">("installed");
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  // ── Fetch installed tool statuses ──────────────────────
  const fetchStatus = useCallback(async () => {
    setFetching(true);
    try {
      const res = await fetch(
        `/api/v1/tools/status?user_id=${userId}&bot_id=${botId}`
      );
      const data = await res.json();
      setInstalled(data.tools ?? []);
      setLastRefresh(new Date());
    } catch {
      showToast("⚠️ Could not reach server");
    } finally {
      setFetching(false);
    }
  }, [userId, botId]);

  // ── Fetch marketplace ──────────────────────────────────
  const fetchMarketplace = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/tools/");
      const data = await res.json();
      setMarketplace(Array.isArray(data) ? data : []);
    } catch {}
  }, []);

  useEffect(() => {
    fetchStatus();
    fetchMarketplace();
    const interval = setInterval(fetchStatus, 15000); // auto-refresh every 15s
    return () => clearInterval(interval);
  }, [fetchStatus, fetchMarketplace]);

  // ── Install tool ───────────────────────────────────────
  const handleInstall = async (toolId: string) => {
    setActionLoading(toolId);
    try {
      const res = await fetch("/api/v1/tools/install", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, bot_id: botId, tool_id: toolId }),
      });
      if (!res.ok) throw new Error();
      showToast("✅ Tool installed and connected!");
      await fetchStatus();
    } catch {
      showToast("❌ Install failed");
    } finally {
      setActionLoading(null);
    }
  };

  // ── Reconnect (re-install) ─────────────────────────────
  const handleReconnect = async (toolId: string) => {
    setActionLoading(toolId);
    try {
      await fetch("/api/v1/tools/install", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, bot_id: botId, tool_id: toolId }),
      });
      showToast("🔄 Reconnected!");
      await fetchStatus();
    } catch {
      showToast("❌ Reconnect failed");
    } finally {
      setActionLoading(null);
    }
  };

  // ── Uninstall ──────────────────────────────────────────
  const handleUninstall = async (toolId: string) => {
    if (!confirm(`Remove ${toolId}?`)) return;
    setActionLoading(toolId);
    // Disconnect from MCP runtime
    try {
      await fetch("/api/v1/mcp/connect/stdio", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, bot_id: botId, name: toolId }),
      }).catch(() => {});
    } finally {}
    showToast("🗑 Tool removed");
    setInstalled((prev) => prev.filter((t) => t.tool_id !== toolId));
    setActionLoading(null);
  };

  const installedIds = new Set(installed.map((t) => t.tool_id));
  const connectedCount = installed.filter((t) => t.connected).length;
  const disconnectedCount = installed.filter((t) => !t.connected).length;

  return (
    <Layout>
      {/* ── Toast ────────────────────────────────────── */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 px-4 py-3 rounded-xl bg-slate-800 border border-slate-600 text-white text-sm shadow-xl animate-fade-in">
          {toast}
        </div>
      )}

      <div className="flex flex-col h-full overflow-y-auto bg-slate-950 text-white px-6 py-8 max-w-4xl mx-auto w-full">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Plug size={22} className="text-violet-400" />
              <h1 className="text-2xl font-bold text-white">Connections</h1>
              <span className="text-xs px-2 py-0.5 bg-violet-600/20 text-violet-300 border border-violet-500/30 rounded-full">
                Bot #{botId}
              </span>
            </div>
            <p className="text-slate-400 text-sm">
              Manage MCP tools, OAuth integrations, and live connection status.
            </p>
          </div>

          <button
            onClick={fetchStatus}
            disabled={fetching}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-600 text-sm text-slate-300 hover:text-white transition-all"
          >
            <RefreshCw size={14} className={fetching ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>

        {/* Stats */}
        <div className="mb-6">
          <StatsBar
            total={installed.length}
            connected={connectedCount}
            disconnected={disconnectedCount}
          />
          {lastRefresh && (
            <p className="text-slate-600 text-xs mt-2 text-right">
              Last refreshed: {lastRefresh.toLocaleTimeString()}
            </p>
          )}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 p-1 bg-slate-900 border border-slate-700/60 rounded-xl mb-6 w-fit">
          {(["installed", "marketplace"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                tab === t
                  ? "bg-violet-600 text-white shadow"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              {t === "installed" ? (
                <span className="flex items-center gap-1.5">
                  <Wifi size={13} /> Installed ({installed.length})
                </span>
              ) : (
                <span className="flex items-center gap-1.5">
                  <Sparkles size={13} /> Marketplace ({marketplace.length})
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── Installed Tools Tab ─────────────────────── */}
        {tab === "installed" && (
          <div>
            {fetching && installed.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-slate-500">
                <RefreshCw size={28} className="animate-spin mb-3" />
                <p>Fetching live connection statuses...</p>
              </div>
            ) : installed.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-slate-500 gap-3">
                <WifiOff size={40} className="text-slate-700" />
                <p className="font-medium">No tools installed yet</p>
                <p className="text-xs text-slate-600">
                  Browse the Marketplace tab to add your first tool.
                </p>
                <button
                  onClick={() => setTab("marketplace")}
                  className="mt-2 flex items-center gap-1.5 px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-xl text-sm"
                >
                  <ChevronRight size={14} /> Open Marketplace
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {/* Offline warning banner */}
                {disconnectedCount > 0 && (
                  <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-amber-500/10 border border-amber-500/25 text-amber-300 text-sm mb-4">
                    <AlertTriangle size={16} />
                    <span>
                      <strong>{disconnectedCount}</strong> tool
                      {disconnectedCount > 1 ? "s are" : " is"} offline. Click{" "}
                      <strong>Reconnect</strong> to restore.
                    </span>
                  </div>
                )}
                {installed.map((tool) => (
                  <InstalledCard
                    key={tool.tool_id}
                    tool={tool}
                    onReconnect={handleReconnect}
                    onUninstall={handleUninstall}
                    loading={actionLoading === tool.tool_id}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Marketplace Tab ─────────────────────────── */}
        {tab === "marketplace" && (
          <div className="space-y-3">
            {marketplace.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-slate-500 gap-3">
                <Package size={40} className="text-slate-700" />
                <p>Marketplace is empty</p>
              </div>
            ) : (
              marketplace.map((tool) => (
                <MarketplaceCard
                  key={tool.id}
                  tool={tool}
                  installed={installedIds.has(tool.id)}
                  onInstall={handleInstall}
                  loading={actionLoading === tool.id}
                />
              ))
            )}
          </div>
        )}
      </div>
    </Layout>
  );
}
