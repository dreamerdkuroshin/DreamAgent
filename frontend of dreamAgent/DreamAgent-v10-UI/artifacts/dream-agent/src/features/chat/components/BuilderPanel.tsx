import { useState, useEffect, useRef, useCallback } from "react";
import {
  Download, Play, SplitSquareHorizontal, FileCode2, Maximize2, Minimize2,
  PanelRightClose, Loader2, GitCommit, ChevronRight, File, FolderOpen,
  AlertTriangle, RefreshCw, Undo2, Redo2, Rocket, ExternalLink, Copy, Check,
  Sparkles, X, ShieldCheck, BarChart3, Zap
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui-elements";

/* ── Types ─────────────────────────────────────────────────── */

interface Version {
  version: number;
  message: string;
  is_active: boolean;
  created_at: string;
}

interface FileEntry { path: string; size: number; }

interface Suggestion {
  title: string;
  description: string;
  impact: "high" | "medium" | "low";
  category: string;
}

interface TelemetryStats {
  success_rate: number;
  avg_fix_attempts: number;
  deploy_success_rate: number;
  counts: Record<string, number>;
}

interface DryRunResult {
  files: { path: string; size: number }[];
  file_count: number;
  size_bytes: number;
  warnings: string[];
  ready: boolean;
}

const EXT_COLORS: Record<string, string> = {
  html: "text-orange-400", css: "text-blue-400", js: "text-yellow-400",
  ts: "text-blue-300", tsx: "text-cyan-400", jsx: "text-yellow-300",
  md: "text-green-400", json: "text-amber-400", py: "text-green-300",
};
const IMPACT_COLORS = { high: "text-red-400 bg-red-500/10 border-red-500/20", medium: "text-amber-400 bg-amber-500/10 border-amber-500/20", low: "text-green-400 bg-green-500/10 border-green-500/20" };

function getExt(path: string) { return path.split(".").pop() || ""; }

/* ── Main Component ────────────────────────────────────────── */

export function BuilderPanel({
  sessionId, onClose, isFocusMode, setFocusMode
}: {
  sessionId: string; onClose: () => void; isFocusMode: boolean; setFocusMode: (v: boolean) => void;
}) {
  const [activeTab, setActiveTab] = useState<"code" | "preview" | "split">("split");
  const [versions, setVersions] = useState<Version[]>([]);
  const [activeVersion, setActiveVersion] = useState(1);
  const maxVersion = Math.max(...versions.map(v => v.version), 1);
  const [loadingAction, setLoadingAction] = useState<string | null>(null);

  // Files
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState("");
  const [fileLoading, setFileLoading] = useState(false);

  // Error & iframe
  const [iframeError, setIframeError] = useState<{ message: string; file?: string; line?: number | null } | null>(null);
  const [iframeKey, setIframeKey] = useState(0);
  const codeContainerRef = useRef<HTMLDivElement>(null);
  const [leftWidth, setLeftWidth] = useState(45);

  // Diff view
  const [diffViewActive, setDiffViewActive] = useState(false);
  const [diffData, setDiffData] = useState<any[] | null>(null);

  // Deploy
  const [deployModalOpen, setDeployModalOpen] = useState(false);
  const [vercelToken, setVercelToken] = useState("");
  const [deployStatus, setDeployStatus] = useState<"idle" | "deploying" | "success" | "error">("idle");
  const [deployUrl, setDeployUrl] = useState("");
  const [deployMsg, setDeployMsg] = useState("");
  const [copiedLink, setCopiedLink] = useState(false);
  const [deployMode, setDeployMode] = useState<"token" | "cli">("token");

  // Dry Run
  const [dryRunOpen, setDryRunOpen] = useState(false);
  const [dryRunData, setDryRunData] = useState<DryRunResult | null>(null);
  const [dryRunLoading, setDryRunLoading] = useState(false);

  // Suggestions
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);

  // Telemetry
  const [telemetry, setTelemetry] = useState<TelemetryStats | null>(null);

  // Progress bar (mapped from SSE)
  const [buildProgress, setBuildProgress] = useState(0);
  const [buildStep, setBuildStep] = useState("");

  /* ── Fetchers ──────────────────────────────────────────── */

  const fetchVersions = useCallback(async () => {
    try {
      const res = await fetch(`/api/v1/builder/versions/${sessionId}`);
      if (res.ok) { const d = await res.json(); setVersions(d.versions ?? []); setActiveVersion(d.current_version ?? 1); }
    } catch {}
  }, [sessionId]);

  const fetchFileTree = useCallback(async (v?: number) => {
    try {
      const res = await fetch(`/api/v1/builder/files/${sessionId}?v=${v ?? activeVersion}`);
      if (res.ok) {
        const d = await res.json();
        const tree: FileEntry[] = d.files ?? [];
        setFiles(tree);
        if (!selectedFile && tree.length > 0) setSelectedFile((tree.find(f => f.path === "index.html") ?? tree[0]).path);
      }
    } catch {}
  }, [sessionId, activeVersion, selectedFile]);

  const loadFileContent = useCallback(async (path: string) => {
    setFileLoading(true);
    setDiffViewActive(false);
    try {
      const res = await fetch(`/api/v1/builder/file/${sessionId}?path=${encodeURIComponent(path)}&v=${activeVersion}`);
      if (res.ok) {
        const d = await res.json();
        setFileContent(d.content ?? "");
        if (iframeError?.file === path && iframeError.line) {
          setTimeout(() => {
            const el = document.getElementById(`code-line-${iframeError.line}`);
            if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" }); el.classList.add("bg-red-500/20"); setTimeout(() => el.classList.remove("bg-red-500/20"), 3000); }
          }, 100);
        }
      }
    } catch { setFileContent("// Error loading file"); } finally { setFileLoading(false); }
  }, [sessionId, activeVersion, iframeError]);

  const fetchTelemetry = useCallback(async () => {
    try {
      const res = await fetch(`/api/v1/builder/telemetry/${sessionId}`);
      if (res.ok) setTelemetry(await res.json());
    } catch {}
  }, [sessionId]);

  const fetchSuggestions = useCallback(async () => {
    setSuggestionsLoading(true);
    try {
      const res = await fetch(`/api/v1/builder/suggest/${sessionId}`);
      if (res.ok) {
        const d = await res.json();
        if (d.suggestions?.length > 0) setSuggestions(d.suggestions);
      }
    } catch {} finally { setSuggestionsLoading(false); }
  }, [sessionId]);

  /* ── Effects ───────────────────────────────────────────── */

  useEffect(() => { fetchVersions(); fetchFileTree(); fetchTelemetry(); const i = setInterval(fetchVersions, 5000); return () => clearInterval(i); }, [sessionId]);
  useEffect(() => { if (selectedFile) loadFileContent(selectedFile); }, [selectedFile, activeVersion]);

  // Live Progress Hook
  useEffect(() => {
    const handleProgress = (e: any) => {
      if (e.detail) {
        setBuildProgress(e.detail.progress);
        setBuildStep(e.detail.message || "");
        
        // Auto-refresh when finished
        if (e.detail.progress >= 100) {
           setTimeout(() => {
             fetchFileTree();
             setIframeKey(k => k + 1); // Ping fresh preview
           }, 800);
           // Fade out bar after short delay
           setTimeout(() => setBuildProgress(0), 3000);
        }
      }
    };
    window.addEventListener("builder:progress", handleProgress);
    return () => window.removeEventListener("builder:progress", handleProgress);
  }, [fetchFileTree, setIframeKey]);

  /* ── Actions ───────────────────────────────────────────── */

  const handleRollback = async (v: number) => {
    if (v < 1 || v > maxVersion) return;
    setLoadingAction(`rollback-${v}`);
    try {
      const res = await fetch("/api/v1/builder/rollback", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sessionId, target_version: v }) });
      if (res.ok) { await fetchVersions(); await fetchFileTree(v); setIframeError(null); setIframeKey(k => k + 1); fetchTelemetry(); }
    } finally { setLoadingAction(null); }
  };

  const loadDiff = async (vTarget: number) => {
    setLoadingAction(`diff-${vTarget}`);
    try {
      const vBase = Math.max(1, vTarget - 1);
      const res = await fetch(`/api/v1/builder/diff/${sessionId}?v1=${vBase}&v2=${vTarget}`);
      if (res.ok) { setDiffData((await res.json()).diffs); setDiffViewActive(true); setActiveTab("code"); }
    } finally { setLoadingAction(null); }
  };

  const handleDryRun = async () => {
    if (!vercelToken.startsWith("vercel_")) { setDeployMsg("Token must start with 'vercel_'"); setDeployStatus("error"); return; }
    setDryRunLoading(true);
    try {
      const res = await fetch("/api/v1/builder/deploy/dry-run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sessionId, vercel_token: vercelToken }) });
      if (res.ok) { setDryRunData(await res.json()); setDryRunOpen(true); }
    } finally { setDryRunLoading(false); }
  };

  const handleDeploy = async () => {
    if (deployMode === "token" && !vercelToken.startsWith("vercel_")) { setDeployStatus("error"); setDeployMsg("Token must start with 'vercel_'"); return; }
    
    setDeployStatus("deploying"); setDeployMsg(deployMode === "token" ? "Uploading files..." : "Running Vercel CLI...");
    
    try {
      if (deployMode === "token") {
        const res = await fetch("/api/v1/builder/deploy/vercel", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sessionId, vercel_token: vercelToken }) });
        if (!res.ok) throw new Error("Deployment rejected");
        const data = await res.json();
        setDeployMsg("Finalizing...");
        setTimeout(() => { setDeployUrl(data.url); setDeployStatus("success"); fetchTelemetry(); }, 1000);
      } else {
        const res = await fetch("/api/v1/builder/deploy/vercel-cli", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sessionId }) });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Deployment rejected");
        
        if (data.requires_login) {
          setDeployStatus("error");
          setDeployMsg(data.message);
          return;
        }
        
        setDeployMsg("Finalizing...");
        setTimeout(() => { setDeployUrl(data.url); setDeployStatus("success"); fetchTelemetry(); }, 1000);
      }
    } catch (e: any) { setDeployStatus("error"); setDeployMsg(e.message || "Deployment failed"); }
  };

  /* ── Render Helpers ────────────────────────────────────── */

  const FileTreeNode = () => {
    const tree: Record<string, FileEntry[]> = {};
    const rootFiles: FileEntry[] = [];
    files.forEach(f => {
      const parts = f.path.split("/");
      if (parts.length === 1) rootFiles.push(f);
      else { const folder = parts[0]; tree[folder] = tree[folder] || []; tree[folder].push({ ...f, path: parts.slice(1).join("/") }); }
    });
    const FileRow = ({ path, realPath }: { path: string; realPath: string }) => (
      <button onClick={() => setSelectedFile(realPath)} className={cn("w-full text-left px-2 py-1 rounded border border-transparent text-xs flex items-center gap-2 transition-all font-mono truncate", selectedFile === realPath ? "bg-primary/10 text-primary border-primary/20" : "hover:bg-white/5 text-white/50 hover:text-white")}>
        <File className={cn("w-3.5 h-3.5 shrink-0", EXT_COLORS[getExt(path)])} />
        <span className="truncate">{path.split("/").pop()}</span>
        {iframeError?.file === realPath && <span className="w-1.5 h-1.5 bg-red-400 rounded-full ml-auto animate-pulse" />}
      </button>
    );
    return (
      <div className="space-y-0.5">
        {rootFiles.map(f => <FileRow key={f.path} path={f.path} realPath={f.path} />)}
        {Object.entries(tree).map(([folder, children]) => (
          <div key={folder}>
            <div className="px-2 py-1 text-xs text-white/40 flex items-center gap-1.5 font-mono"><FolderOpen className="w-3.5 h-3.5 text-amber-400/60" />{folder}</div>
            <div className="pl-3">{children.map(f => <FileRow key={f.path} path={f.path} realPath={folder + "/" + f.path} />)}</div>
          </div>
        ))}
      </div>
    );
  };

  const previewSrc = `/api/v1/builder/preview/${sessionId}?v=${activeVersion}`;
  const c = telemetry?.counts;

  return (
    <div className="h-full flex flex-col bg-[#0b0b10] rounded-2xl overflow-hidden border border-white/10 shadow-2xl relative">

      {/* ── Progress Bar ─────────────────────────────────────── */}
      {buildProgress > 0 && buildProgress < 100 && (
        <div className="absolute top-0 left-0 right-0 z-30 h-1 bg-black/40">
          <div className="h-full bg-gradient-to-r from-primary to-cyan-300 transition-all duration-700 ease-out rounded-r" style={{ width: `${buildProgress}%` }} />
        </div>
      )}

      {/* ── Top Bar ──────────────────────────────────────────── */}
      <div className="flex-none px-3 py-2 border-b border-white/5 flex items-center justify-between bg-black/60 z-20">
        <div className="flex gap-1 bg-white/5 p-1 rounded-xl">
          {([["code", "Code", FileCode2], ["preview", "Preview", Play], ["split", "Split", SplitSquareHorizontal]] as const).map(([id, label, Icon]) => (
            <button key={id} onClick={() => setActiveTab(id as any)} className={cn("px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all", activeTab === id ? "bg-primary text-black shadow-[0_0_10px_rgba(0,240,255,0.4)]" : "text-white/50 hover:text-white")}>
              <Icon className="w-3.5 h-3.5" /> {label}
            </button>
          ))}
        </div>

        <div className="flex bg-white/5 rounded-xl p-1 gap-0.5 border border-white/5 hidden sm:flex">
          <button onClick={() => handleRollback(activeVersion - 1)} disabled={activeVersion <= 1} className="p-1.5 rounded-lg hover:bg-white/10 disabled:opacity-30 transition-all" title="Undo"><Undo2 className="w-4 h-4 text-white/70" /></button>
          <button onClick={() => handleRollback(activeVersion + 1)} disabled={activeVersion >= maxVersion} className="p-1.5 rounded-lg hover:bg-white/10 disabled:opacity-30 transition-all" title="Redo"><Redo2 className="w-4 h-4 text-white/70" /></button>
        </div>

        <div className="flex items-center gap-1.5">
          <button onClick={fetchSuggestions} disabled={suggestionsLoading} className="p-2 rounded-lg text-amber-400/70 hover:text-amber-400 hover:bg-amber-500/10 transition-all" title="Get AI Suggestions">
            {suggestionsLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          </button>
          <button onClick={() => { setIframeKey(k => k + 1); setIframeError(null); }} className="p-2 rounded-lg text-white/50 hover:text-white hover:bg-white/5"><RefreshCw className="w-4 h-4" /></button>
          <a href={`/api/v1/builder/download/${sessionId}`} target="_blank" rel="noreferrer" className="p-2 rounded-lg text-white/50 hover:text-white hover:bg-white/5"><Download className="w-4 h-4" /></a>
          <button onClick={() => setDeployModalOpen(true)} className="px-3 py-1.5 bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30 border border-cyan-500/30 rounded-lg transition-all flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide">
            <Rocket className="w-3.5 h-3.5" /> Deploy
          </button>
          <button onClick={() => setFocusMode(!isFocusMode)} className="p-2 rounded-lg text-white/50 hover:text-white hover:bg-white/5">
            {isFocusMode ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
          <button onClick={onClose} className="p-2 text-red-400 hover:bg-red-500/20 rounded-lg"><PanelRightClose className="w-4 h-4" /></button>
        </div>
      </div>

      {/* ── AI Suggestion Chips ──────────────────────────────── */}
      {suggestions.length > 0 && (
        <div className="flex-none px-3 py-2 border-b border-white/5 bg-amber-500/5 flex items-center gap-2 overflow-x-auto custom-scrollbar">
          <Sparkles className="w-4 h-4 text-amber-400 shrink-0" />
          {suggestions.map((s, i) => (
            <div key={i} className={cn("shrink-0 px-3 py-1.5 rounded-xl border text-xs flex items-center gap-2 group relative", IMPACT_COLORS[s.impact])}>
              <span className="font-semibold">{s.title}</span>
              <button onClick={() => setSuggestions(suggestions.filter((_, j) => j !== i))} className="opacity-0 group-hover:opacity-100 transition-opacity"><X className="w-3 h-3" /></button>
              {/* Hover tooltip */}
              <div className="pointer-events-none absolute bottom-full left-0 mb-2 w-64 opacity-0 group-hover:opacity-100 transition-all bg-black/95 border border-white/10 p-3 rounded-xl shadow-2xl z-50">
                <p className="text-white/80 text-xs">{s.description}</p>
                <div className="flex items-center gap-2 mt-2 text-[10px]">
                  <span className={cn("px-1.5 py-0.5 rounded uppercase font-bold", IMPACT_COLORS[s.impact])}>{s.impact}</span>
                  <span className="text-white/40">{s.category}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Content Area ─────────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden min-h-0">
        {(activeTab === "code" || activeTab === "split") && (
          <div className="h-full bg-[#050508] border-r border-white/5 flex flex-col pt-2 w-[180px] shrink-0"><FileTreeNode /></div>
        )}

        {(activeTab === "code" || activeTab === "split") && (
          <div className="h-full flex flex-col bg-[#0d0d12] overflow-hidden" style={{ width: activeTab === "split" ? `${leftWidth}%` : "100%" }}>
            {diffViewActive ? (
              <div className="flex-1 overflow-auto p-4 font-mono text-xs custom-scrollbar">
                <div className="flex items-center justify-between mb-4 border-b border-white/10 pb-2">
                  <span className="text-cyan-400 font-bold">Diff View (v{activeVersion})</span>
                  <button onClick={() => setDiffViewActive(false)} className="text-white/50 hover:text-white px-2 py-1 rounded bg-white/5 text-[10px]">Exit Diff</button>
                </div>
                {diffData?.length === 0 && <div className="text-white/30 text-center py-10 italic">No changes detected</div>}
                {diffData?.map(d => (
                  <div key={d.file} className="mb-4 border border-white/5 rounded-lg overflow-hidden bg-black/40">
                    <div className="bg-white/5 px-3 py-1.5 font-bold text-white/70 flex items-center gap-2 text-[11px]"><File className="w-3 h-3" /> {d.file}</div>
                    <div className="p-2 space-y-0.5 whitespace-pre overflow-x-auto text-[11px]">
                      {d.changes.map((c: any, i: number) => (
                        <div key={i} className={cn("px-2 py-0.5 rounded", c.type === "added" ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400")}>
                          {c.type === "added" ? "+ " : "- "}{c.line}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex-1 overflow-auto custom-scrollbar pt-1" ref={codeContainerRef}>
                {!selectedFile ? (
                  <div className="h-full flex flex-col items-center justify-center text-white/20"><FileCode2 className="w-12 h-12 mb-3 opacity-30" /><p className="text-xs">Select a file</p></div>
                ) : (
                  <table className="w-full text-xs font-mono text-left"><tbody>
                    {fileContent.split("\n").map((line, i) => (
                      <tr key={i} id={`code-line-${i + 1}`} className="hover:bg-white/5 transition-colors">
                        <td className="w-10 pr-2 pl-2 text-right text-white/20 border-r border-white/5 select-none bg-[#0d0d12]">{i + 1}</td>
                        <td className="pl-4 pr-2 whitespace-pre text-white/80">{line || " "}</td>
                      </tr>
                    ))}
                  </tbody></table>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === "split" && <div className="w-1 bg-white/10 shrink-0" />}

        {(activeTab === "preview" || activeTab === "split") && (
          <div className="h-full flex flex-col relative bg-white" style={{ width: activeTab === "split" ? `${100 - leftWidth}%` : "100%" }}>
            {iframeError && (
              <div className="absolute top-4 left-4 right-4 z-20 animate-in fade-in slide-in-from-top-4">
                <div className="bg-black/90 backdrop-blur-xl border border-red-500/40 p-4 rounded-xl shadow-2xl flex flex-col gap-2 relative overflow-hidden">
                  <div className="absolute top-0 left-0 w-1 h-full bg-red-500" />
                  <div className="flex items-center gap-2 text-red-400 font-bold text-sm"><AlertTriangle className="w-4 h-4" /> Build Error</div>
                  <div className="font-mono text-xs text-white/80 bg-red-500/5 p-2 rounded border border-red-500/10">
                    <span className="text-white/40">[{iframeError.file || "unknown"}:{iframeError.line || "?"}]</span> {iframeError.message}
                  </div>
                  {iframeError.file && <Button size="sm" variant="ghost" onClick={() => { setActiveTab("code"); setSelectedFile(iframeError.file!); }} className="self-end text-xs h-7 text-cyan-400">Jump to File</Button>}
                </div>
              </div>
            )}
            <iframe key={iframeKey} src={previewSrc} className="w-full h-full border-none bg-white" sandbox="allow-scripts allow-same-origin" title="Preview" />
          </div>
        )}
      </div>

      {/* ── Deploy Modal ─────────────────────────────────────── */}
      {deployModalOpen && (
        <div className="absolute inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0b0b10] border border-white/10 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl animate-in zoom-in-95">
            <div className="p-4 border-b border-white/5 flex justify-between items-center bg-black/40">
              <div className="font-bold text-white flex items-center gap-2"><Rocket className="w-4 h-4 text-cyan-400" /> Deploy to Vercel</div>
              <button onClick={() => { setDeployModalOpen(false); setDryRunOpen(false); setDeployStatus("idle"); }} className="text-white/40 hover:text-white"><X className="w-4 h-4" /></button>
            </div>
            <div className="p-6 space-y-4">
              {deployStatus === "idle" || deployStatus === "error" ? (
                <>
                  <div className="flex bg-white/5 rounded-xl border border-white/10 p-1 mb-2">
                    <button onClick={() => setDeployMode("token")} className={cn("flex-1 text-xs py-1.5 rounded-lg font-bold transition-all", deployMode === "token" ? "bg-primary/20 text-primary" : "text-white/50 hover:text-white")}>Cloud Token</button>
                    <button onClick={() => setDeployMode("cli")} className={cn("flex-1 text-xs py-1.5 rounded-lg font-bold transition-all", deployMode === "cli" ? "bg-primary/20 text-primary" : "text-white/50 hover:text-white")}>Local CLI</button>
                  </div>
                  
                  <p className="text-sm text-white/60 mb-2">
                    {deployMode === "token" ? "Push your project live to the web via Vercel API." : "Deploy using the Vercel CLI installed on this machine."}
                  </p>
                  
                  {deployStatus === "error" && deployMsg.includes("login") ? (
                     <div className="text-xs space-y-2 bg-red-500/10 border border-red-500/20 p-3 rounded-xl text-red-400">
                       <div className="font-bold flex items-center gap-1.5"><AlertTriangle className="w-4 h-4" /> Auth Required</div>
                       <p>You must authenticate your local Vercel CLI before deploying.</p>
                       <div className="bg-black/50 p-2 rounded border border-red-500/10 font-mono text-[11px] select-all">
                         npx vercel login
                       </div>
                     </div>
                  ) : deployStatus === "error" && (
                    <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 p-2 rounded break-words whitespace-pre-wrap max-h-32 overflow-auto">
                      {deployMsg}
                    </div>
                  )}

                  {deployMode === "token" && (
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold text-white/50 uppercase tracking-widest block">Vercel API Token</label>
                      <input type="password" value={vercelToken} onChange={e => setVercelToken(e.target.value)} placeholder="vercel_xxxxxxx" className="w-full bg-black/50 border border-white/10 rounded-xl px-3 py-2 text-sm text-white outline-none focus:border-cyan-500/50" />
                    </div>
                  )}

                  {/* Dry Run Result */}
                  {dryRunOpen && dryRunData && (
                    <div className="bg-black/40 border border-white/10 rounded-xl p-3 space-y-2 text-xs">
                      <div className="flex items-center gap-2 font-bold text-white/80"><ShieldCheck className="w-4 h-4 text-cyan-400" /> Dry Run Report</div>
                      <div className="flex gap-4 text-white/60">
                        <span>📦 {dryRunData.file_count} files</span>
                        <span>📏 {(dryRunData.size_bytes / 1024).toFixed(1)}KB</span>
                      </div>
                      {dryRunData.warnings.length > 0 && (
                        <div className="space-y-1 mt-1">
                          {dryRunData.warnings.map((w, i) => (
                            <div key={i} className="flex items-center gap-1.5 text-amber-400"><AlertTriangle className="w-3 h-3 shrink-0" /> {w}</div>
                          ))}
                        </div>
                      )}
                      {dryRunData.ready && <div className="text-green-400 font-bold flex items-center gap-1.5"><Check className="w-3.5 h-3.5" /> Ready to deploy</div>}
                    </div>
                  )}

                  <div className="flex gap-2 mt-2">
                    <Button onClick={handleDryRun} variant="outline" disabled={dryRunLoading || (deployMode === "token" && !vercelToken)} className="flex-1 border-white/10 text-white text-xs h-10">
                      {dryRunLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <><ShieldCheck className="w-4 h-4 mr-1.5" /> Test Deploy</>}
                    </Button>
                    <Button onClick={handleDeploy} disabled={deployMode === "token" && !vercelToken} className="flex-1 text-xs h-10 font-bold uppercase tracking-wider shadow-[0_0_15px_rgba(0,240,255,0.2)]">
                      <Rocket className="w-4 h-4 mr-1.5" /> Launch
                    </Button>
                  </div>
                </>
              ) : deployStatus === "deploying" ? (
                <div className="flex flex-col items-center justify-center py-6 gap-4">
                  <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
                  <div className="text-sm font-bold text-white animate-pulse">{deployMsg}</div>
                  <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden"><div className="h-full bg-cyan-400 animate-pulse w-2/3 rounded-full" /></div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-4 gap-4 text-center">
                  <div className="w-12 h-12 rounded-full bg-green-500/20 border border-green-500/40 flex items-center justify-center text-green-400"><Check className="w-6 h-6" /></div>
                  <div className="text-white font-bold text-lg">Deployed! 🚀</div>
                  <div className="bg-black/50 border border-white/10 p-3 rounded-xl w-full flex items-center gap-2">
                    <a href={deployUrl} target="_blank" rel="noreferrer" className="text-cyan-400 hover:text-cyan-300 truncate flex-1 text-sm font-mono text-left">{deployUrl}</a>
                    <button onClick={() => { navigator.clipboard.writeText(deployUrl); setCopiedLink(true); }} className="p-1 hover:bg-white/10 rounded text-white/60 hover:text-white">
                      {copiedLink ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                    </button>
                  </div>
                  <a href={deployUrl} target="_blank" rel="noreferrer" className="w-full"><Button variant="outline" className="w-full border-white/10">Open Live Site <ExternalLink className="w-4 h-4 ml-2" /></Button></a>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Version Footer + Telemetry ───────────────────────── */}
      <div className="flex-none px-3 py-2 border-t border-white/5 bg-black/60 flex items-center justify-between gap-3">
        {/* Versions */}
        <div className="flex items-center gap-2 overflow-x-auto custom-scrollbar flex-1 min-w-0">
          <GitCommit className="w-4 h-4 text-white/30 shrink-0" />
          {versions.map(v => (
            <div key={v.version} className="relative group shrink-0">
              <button onClick={() => !v.is_active && handleRollback(v.version)} disabled={v.is_active || loadingAction === `rollback-${v.version}`} className={cn("px-3 py-1 rounded-lg text-[10px] font-bold border flex items-center gap-1.5 transition-all font-mono", v.is_active ? "bg-primary/15 text-primary border-primary/30" : "bg-white/5 text-white/50 border-white/5 hover:bg-white/10 hover:text-white")}>
                {loadingAction === `rollback-${v.version}` ? <Loader2 className="w-3 h-3 animate-spin" /> : <span>v{v.version}</span>}
                {v.is_active && <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />}
              </button>
              <div className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 min-w-[200px] opacity-0 group-hover:opacity-100 group-hover:pointer-events-auto transition-all bg-black/95 border border-white/10 px-3 py-2 rounded-xl shadow-2xl z-50 flex flex-col gap-2">
                <div>
                  <p className="text-[11px] text-white/80 font-bold">{v.message || "No message"}</p>
                  <p className="text-[9px] text-white/40 mt-0.5">{v.created_at?.slice(0, 16)}</p>
                </div>
                <div className="h-px bg-white/10 w-full" />
                <div className="flex items-center gap-1.5">
                  {!v.is_active && <button onClick={() => handleRollback(v.version)} className="flex-1 bg-white/5 hover:bg-white/10 text-white/80 text-[10px] py-1 rounded">Rollback</button>}
                  {v.version > 1 && <button onClick={() => loadDiff(v.version)} className="flex-1 bg-primary/10 hover:bg-primary/20 text-primary text-[10px] py-1 rounded border border-primary/20">{loadingAction === `diff-${v.version}` ? "..." : "View Diff"}</button>}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Telemetry Stats */}
        {c && (
          <div className="flex items-center gap-3 text-[10px] font-mono shrink-0 border-l border-white/10 pl-3">
            <span className="text-green-400 flex items-center gap-1"><Zap className="w-3 h-3" /> {c.update_success ?? 0}</span>
            <span className="text-red-400 flex items-center gap-1"><X className="w-3 h-3" /> {c.update_fail ?? 0}</span>
            <span className="text-amber-400 flex items-center gap-1"><RefreshCw className="w-3 h-3" /> {c.rollback ?? 0}</span>
            <span className="text-cyan-400 flex items-center gap-1"><Rocket className="w-3 h-3" /> {c.deploy_success ?? 0}</span>
          </div>
        )}
      </div>
    </div>
  );
}
