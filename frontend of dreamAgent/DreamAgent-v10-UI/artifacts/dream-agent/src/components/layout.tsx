import { useState, useEffect } from "react";
import { Link, useLocation } from "wouter";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Cpu,
  MessageSquare,
  CheckSquare,
  History,
  Settings,
  Menu,
  X,
  Sparkles,
  BarChart3,
  RefreshCw,
  Zap,
  Plug,
  MonitorPlay,
} from "lucide-react";
import { useAppStore } from "@/store/app.store";

const coreNavItems = [
  { href: "/", label: "Chat", icon: MessageSquare },
  { href: "/builder", label: "Builder", icon: MonitorPlay },
  { href: "/tasks", label: "Tasks", icon: CheckSquare },
  { href: "/connections", label: "Connections", icon: Plug },
  { href: "/activity", label: "Activity", icon: History },
  { href: "/settings", label: "Settings", icon: Settings },
];

const advancedNavItems = [
  { href: "/agents", label: "Agents", icon: Cpu },
  { href: "/monitoring", label: "Monitoring", icon: BarChart3 },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const [location] = useLocation();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const { mode, setMode } = useAppStore();
  const [override, setOverride] = useState("auto");

  useEffect(() => {
    fetch("/api/v1/settings/mode")
      .then(res => res.json())
      .then(d => {
        if (d?.data?.override) setOverride(d.data.override);
        const name = d?.data?.mode_name;
        if (name === "lite") setMode("Lite");
        else if (name === "ultra") setMode("Ultra");
        else setMode("Standard");
      })
      .catch(() => {});
  }, [setMode]);

  const handleModeChange = async (val: string) => {
    setOverride(val);
    try {
      const res = await fetch("/api/v1/settings/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: val })
      });
      const d = await res.json();
      if (d?.data?.mode_name) {
        const title = d.data.mode_name;
        setMode(title === "lite" ? "Lite" : title === "ultra" ? "Ultra" : "Standard");
      }
    } catch {}
  };

  return (
    <div className="min-h-screen bg-background flex flex-col md:flex-row overflow-hidden selection:bg-primary/30 selection:text-primary">
      {/* Mobile Topbar */}
      <div className="md:hidden flex items-center justify-between p-4 border-b border-border bg-card/80 backdrop-blur-md z-50">
        <div className="flex items-center gap-2 text-primary font-display font-bold text-xl">
          <Sparkles className="w-6 h-6" />
          <span>DreamAgent</span>
        </div>
        <button onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} className="text-foreground">
          {isMobileMenuOpen ? <X /> : <Menu />}
        </button>
      </div>

      {/* Sidebar */}
      <aside className={cn(
        "fixed md:static inset-y-0 left-0 w-64 glass-panel z-40 transition-transform duration-300 ease-in-out md:translate-x-0 flex flex-col",
        isMobileMenuOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <div className="p-6 hidden md:flex items-center gap-3 text-transparent bg-clip-text bg-gradient-to-r from-primary to-secondary font-display font-extrabold text-2xl tracking-tighter">
          <Sparkles className="w-8 h-8 text-primary" />
          DreamAgent
        </div>

        <nav className="flex-1 px-4 py-4 space-y-1 overflow-y-auto custom-scrollbar">
          <div className="mb-2 px-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Core</div>
          {coreNavItems.map((item) => {
            const isActive = location === item.href || (item.href !== "/" && location.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setIsMobileMenuOpen(false)}
                className={cn(
                  "flex items-center gap-3 px-4 py-3 rounded-xl font-medium transition-all duration-200 group relative",
                  isActive
                    ? "bg-primary/10 text-primary border border-primary/20 neon-border"
                    : "text-muted-foreground hover:bg-white/5 hover:text-foreground"
                )}
              >
                <item.icon className={cn("w-5 h-5 transition-transform duration-300", isActive && "scale-110")} />
                {item.label}
                {isActive && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-primary rounded-r-full shadow-[0_0_10px_rgba(0,240,255,0.8)]" />
                )}
              </Link>
            );
          })}

          {(mode === 'Standard' || mode === 'Ultra') && (
            <>
              <div className="mt-8 mb-2 px-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
                <Zap className="w-3 h-3 text-secondary" /> Advanced
              </div>
              {advancedNavItems.map((item) => {
                const isActive = location === item.href || (item.href !== "/" && location.startsWith(item.href));
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setIsMobileMenuOpen(false)}
                    className={cn(
                      "flex items-center gap-3 px-4 py-3 rounded-xl font-medium transition-all duration-200 group relative",
                      isActive
                        ? "bg-secondary/10 text-secondary border border-secondary/20 shadow-[0_0_10px_rgba(139,92,246,0.2)]"
                        : "text-muted-foreground hover:bg-white/5 hover:text-foreground"
                    )}
                  >
                    <item.icon className={cn("w-5 h-5 transition-transform duration-300", isActive && "scale-110")} />
                    {item.label}
                    {isActive && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-secondary rounded-r-full shadow-[0_0_10px_rgba(139,92,246,0.8)]" />
                    )}
                  </Link>
                );
              })}
            </>
          )}
        </nav>

        <div className="p-4 border-t border-white/5 space-y-4">
          <div className="px-1">
            <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest block mb-2">Performance Mode</label>
            <select
              value={override}
              onChange={(e) => handleModeChange(e.target.value)}
              className="flex h-9 w-full rounded-lg border border-white/10 bg-black/40 px-3 text-xs text-foreground focus:outline-none focus:border-primary appearance-none hover:border-white/20 transition-all cursor-pointer"
            >
              <option value="auto">Auto (Detect)</option>
              <option value="lite">Lite (Low RAM)</option>
              <option value="standard">Standard (Stable)</option>
              <option value="ultra">Ultra (Max Perf)</option>
            </select>
          </div>

          <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-black/40 border border-white/5">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-secondary flex items-center justify-center text-black font-bold text-xs shadow-[0_0_15px_rgba(139,92,246,0.4)]">
              DA
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-semibold text-foreground">DreamAgent</span>
              <span className="text-xs text-muted-foreground">v3.0 ({mode})</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto relative z-0">
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary/20 to-transparent" />
        <div className="p-4 md:p-8 max-w-7xl mx-auto min-h-full">
          {children}
        </div>
      </main>
    </div>
  );
}
