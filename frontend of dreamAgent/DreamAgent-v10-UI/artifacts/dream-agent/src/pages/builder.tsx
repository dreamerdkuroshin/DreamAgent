import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Layout } from "@/components/layout";
import { Card, Button, Badge } from "@/components/ui-elements";
import { MonitorPlay, Loader2, RefreshCw, Layers, Clock, CheckCircle2, ChevronRight, Plus } from "lucide-react";
import { useLocation } from "wouter";
import { formatDate } from "@/lib/utils";

interface BuilderSession {
  id: string;
  project_name: string;
  project_type: string;
  design: string;
  version: number;
  status: string;
  file_count: number;
  has_backend: boolean;
  created_at: string;
  updated_at: string;
}

export default function Builder() {
  const [, setLocation] = useLocation();
  const { data: sessions, isLoading, refetch, isRefetching } = useQuery<BuilderSession[]>({
    queryKey: ["/api/v1/builder/sessions"],
    queryFn: async () => {
      const res = await fetch("/api/v1/builder/sessions");
      if (!res.ok) throw new Error("Failed to fetch sessions");
      return res.json();
    }
  });

  const handleUpdate = (sessionId: string) => {
    setLocation(`/?sessionId=${sessionId}`);
  };

  return (
    <Layout>
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8 gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            <span className="text-[10px] font-bold text-primary uppercase tracking-widest">Builder Manifest</span>
          </div>
          <h1 className="text-3xl font-display font-bold text-foreground">Project Hub</h1>
          <p className="text-muted-foreground mt-1">Access and resume your autonomous build sessions.</p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            onClick={() => setLocation("/builder/new")}
            className="px-5 h-9 bg-gradient-to-r from-primary to-secondary text-black font-bold text-xs uppercase tracking-[0.1em] shadow-lg shadow-primary/20 hover:shadow-primary/40 hover:scale-[1.02] transition-all duration-300"
          >
            <Plus className="w-4 h-4 mr-2" /> New Build
          </Button>
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isLoading || isRefetching} className="border-white/10 hover:bg-white/5">
            {isLoading || isRefetching ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <RefreshCw className="w-4 h-4 mr-2" />}
            Refresh
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {isLoading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="h-48 animate-pulse bg-white/5 border-white/5" />
          ))
        ) : sessions?.length === 0 ? (
          <div className="col-span-full py-20 text-center bg-black/20 rounded-3xl border border-white/5 backdrop-blur-xl">
            <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mx-auto mb-4 border border-white/10 shadow-[0_0_20px_rgba(255,255,255,0.05)]">
              <Layers className="w-8 h-8 text-white/20" />
            </div>
            <h3 className="text-lg font-bold text-foreground mb-1">No builds detected</h3>
            <p className="text-sm text-muted-foreground">Start a new conversation to initialize your first project.</p>
          </div>
        ) : (
          sessions?.map((session) => (
            <Card key={session.id} className="group relative overflow-hidden hover:border-primary/40 transition-all duration-500 bg-black/40 backdrop-blur-3xl border-white/10 shadow-2xl hover:shadow-primary/5">
              <div className="absolute top-0 right-0 p-4">
                 <Badge variant={session.status === 'completed' ? 'success' : 'neon'} className="text-[10px] uppercase tracking-tighter px-2 py-0.5 font-bold">
                   {session.status}
                 </Badge>
              </div>
              
              <div className="p-6">
                <div className="flex items-center gap-4 mb-5">
                  <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5 border border-primary/20 flex items-center justify-center text-primary group-hover:scale-110 group-hover:rotate-3 transition-all duration-500 shadow-[0_0_15px_rgba(0,240,255,0.1)]">
                    <MonitorPlay className="w-6 h-6" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="font-bold text-foreground truncate group-hover:text-primary transition-colors text-lg tracking-tight">
                      {session.project_name || "Untitled Build"}
                    </h3>
                    <p className="text-[10px] text-muted-foreground uppercase font-mono tracking-widest flex items-center gap-1.5 mt-0.5">
                      <Layers className="w-3 h-3 opacity-50" /> {session.project_type || "Web App"} • v{session.version}
                    </p>
                  </div>
                </div>

                <div className="space-y-3.5 mb-7 bg-white/5 rounded-2xl p-4 border border-white/5">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className="flex items-center gap-2"><Clock className="w-4 h-4 opacity-50" /> Updated</span>
                    <span className="text-foreground/90 font-medium">{formatDate(session.updated_at)}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4 opacity-50" /> Architecture</span>
                    <span className="text-foreground/90 font-medium">{session.file_count} Source Files</span>
                  </div>
                  {session.has_backend && (
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span className="flex items-center gap-2"><RefreshCw className="w-4 h-4 opacity-50 text-emerald-400/70" /> Backend Node</span>
                      <span className="text-emerald-400 font-bold uppercase text-[9px] bg-emerald-400/10 px-2 py-0.5 rounded-full border border-emerald-400/20 shadow-[0_0_10px_rgba(52,211,153,0.1)]">Active</span>
                    </div>
                  )}
                </div>

                <div className="flex gap-2">
                  <Button 
                    className="flex-1 text-[11px] uppercase font-bold tracking-[0.1em] h-11 bg-primary/10 hover:bg-primary hover:text-black border-primary/20 shadow-lg shadow-black/20 hover:shadow-primary/20 transition-all duration-300"
                    variant="outline"
                    onClick={() => handleUpdate(session.id)}
                  >
                    Launch Builder <ChevronRight className="w-4 h-4 ml-1.5" />
                  </Button>
                  <a href={`/api/v1/builder/download/${session.id}`} target="_blank" rel="noreferrer" className="shrink-0" title="Download Source">
                    <Button variant="ghost" className="h-11 w-11 p-0 border border-white/5 hover:border-white/20 hover:bg-white/10 group/btn rounded-xl">
                       <span className="grayscale group-hover/btn:grayscale-0 transition-all duration-300 text-lg">📁</span>
                    </Button>
                  </a>
                </div>
              </div>

              {/* Hover highlight line */}
              <div className="absolute bottom-0 left-0 h-1 bg-gradient-to-r from-transparent via-primary to-transparent transition-all duration-700 w-0 group-hover:w-full opacity-60" />
              
              {/* Dynamic background glow */}
              <div className="absolute -inset-24 bg-primary/5 rounded-full blur-[100px] opacity-0 group-hover:opacity-100 transition-opacity duration-1000 pointer-events-none" />
            </Card>
          ))
        )}
      </div>
    </Layout>
  );
}
