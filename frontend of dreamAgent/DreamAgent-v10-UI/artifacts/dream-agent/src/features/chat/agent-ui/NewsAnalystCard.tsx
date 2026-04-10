import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Globe2, FileText, Link2, ChevronRight, Activity,
  Zap, TrendingUp, Clock, Shield, AlertTriangle,
  Newspaper, BarChart3, Target, Layers
} from "lucide-react";
import { cn } from "@/lib/utils";

// ─── Types ────────────────────────────────────────────────────────────────────
interface NewsSource { title: string; url: string; }
interface TimelineEntry { date: string; event: string; }
interface PerspectiveGroup { label: string; view: string; strength?: string; countries?: string[]; sources?: string[]; }
interface NewsCluster {
  event_title: string;
  summary?: string;
  impact?: string;        // "low" | "medium" | "high"
  impact_note?: string;
  confidence?: number;    // 0–100
  timeline?: TimelineEntry[];
  facts?: Array<string | { fact: string; confidence?: string; evidence_count?: number; source?: string }>;
  groups?: PerspectiveGroup[];
  sources?: NewsSource[];
}
interface NewsData { clusters: NewsCluster[]; }

// ─── Impact helpers ───────────────────────────────────────────────────────────
const IMPACT_MAP: Record<string, { color: string; dot: string; label: string; icon: React.ReactNode }> = {
  high:   { color: "text-red-400",    dot: "bg-red-400",    label: "High",   icon: <AlertTriangle className="w-3.5 h-3.5" /> },
  medium: { color: "text-amber-400",  dot: "bg-amber-400",  label: "Medium", icon: <TrendingUp   className="w-3.5 h-3.5" /> },
  low:    { color: "text-emerald-400",dot: "bg-emerald-400",label: "Low",    icon: <Shield        className="w-3.5 h-3.5" /> },
};
const impactEmoji: Record<string, string> = { high: "🔴", medium: "🟡", low: "🟢" };

// ─── Confidence Bar ──────────────────────────────────────────────────────────
function ConfidenceBar({ score }: { score: number }) {
  const color = score >= 75 ? "bg-emerald-500" : score >= 50 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <span className="text-[9px] font-bold uppercase tracking-widest text-white/40">AI Confidence</span>
      <div className="flex-1 h-1 rounded-full bg-white/10 overflow-hidden">
        <motion.div
          className={cn("h-full rounded-full", color)}
          initial={{ width: 0 }}
          animate={{ width: `${score}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </div>
      <span className="text-[9px] font-bold text-white/50 tabular-nums">{score}%</span>
    </div>
  );
}

// ─── Skeleton Loader ──────────────────────────────────────────────────────────
function NewsCardSkeleton() {
  return (
    <div className="w-full max-w-4xl space-y-4 my-4 font-sans border border-primary/20 bg-black/40 rounded-2xl p-4 shadow-xl backdrop-blur-md animate-pulse">
      <div className="flex items-center gap-2 pb-2 border-b border-primary/20">
        <div className="w-5 h-5 rounded-full bg-white/10" />
        <div className="h-3 w-32 rounded bg-white/10" />
        <div className="h-3 w-20 rounded-full bg-white/5 ml-2" />
      </div>
      <div className="flex gap-2">
        {[1,2,3].map(i => <div key={i} className="h-6 w-20 rounded-full bg-white/5" />)}
      </div>
      {[1,2].map(i => (
        <div key={i} className="p-4 rounded-xl border border-white/10 bg-black/30 space-y-3">
          <div className="h-5 w-3/4 rounded bg-white/10" />
          <div className="h-3 w-full rounded bg-white/5" />
          <div className="h-3 w-5/6 rounded bg-white/5" />
          <div className="grid grid-cols-2 gap-3 mt-2">
            <div className="h-24 rounded-lg bg-white/5" />
            <div className="h-24 rounded-lg bg-white/5" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
export function NewsAnalystCard({ data, loading }: { data?: NewsData; loading?: boolean }) {
  const [activeTab, setActiveTab] = useState<string>("");

  if (loading) return <NewsCardSkeleton />;
  if (!data?.clusters?.length) return <NewsCardSkeleton />;

  // Collect all unique perspective tabs across all clusters
  const allTabsMap = new Map<string, PerspectiveGroup>();
  data.clusters.forEach((c) => {
    c.groups?.forEach((g) => {
      if (!allTabsMap.has(g.label)) allTabsMap.set(g.label, g);
    });
  });
  const tabs = Array.from(allTabsMap.keys());

  // Default tab to Global if available
  const currentTab = activeTab || (tabs.includes("🌍 Global") ? "🌍 Global" : tabs[0] ?? "");
  if (!activeTab && currentTab) setActiveTab(currentTab);

  const hasLowConfidence = data.clusters.some((c) =>
    c.facts?.some((f) => typeof f !== "string" && f.confidence === "low")
  );

  return (
    <div className="w-full max-w-4xl space-y-4 my-4 font-sans relative">
      {/* Gradient border wrapper */}
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-primary/30 via-cyan-500/10 to-purple-500/20 blur-sm -z-10" />
      <div className="relative border border-primary/25 bg-black/50 rounded-2xl p-4 shadow-2xl backdrop-blur-xl overflow-hidden">

        {/* Subtle top shimmer line */}
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary/60 to-transparent" />

        {/* ── Header ── */}
        <div className="flex items-center justify-between pb-3 border-b border-white/8 mb-3">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-primary/15 border border-primary/25 flex items-center justify-center">
              <Newspaper className="w-4 h-4 text-primary" />
            </div>
            <h3 className="text-sm font-bold uppercase tracking-widest text-primary/90">
              AI Global Analyst
            </h3>
            <span className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-[9px] uppercase font-bold border border-primary/20 ml-1">
              Live Intelligence
            </span>
          </div>
          {hasLowConfidence && (
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-[9px] font-bold uppercase tracking-wide">
              <AlertTriangle className="w-3 h-3" /> Limited Sources
            </div>
          )}
        </div>

        {/* ── Animated Perspective Tabs ── */}
        {tabs.length > 0 && (
          <div className="flex items-center gap-2 overflow-x-auto pb-3 mb-4 custom-scrollbar">
            {tabs.map((t) => {
              const isActive = currentTab === t;
              return (
                <button
                  key={t}
                  onClick={() => setActiveTab(t)}
                  title={allTabsMap.get(t)?.countries?.join(", ")}
                  className={cn(
                    "relative px-3 py-1.5 rounded-full text-xs font-bold whitespace-nowrap transition-all duration-300 border flex items-center gap-1.5 overflow-hidden",
                    isActive
                      ? "text-black border-primary shadow-[0_0_20px_rgba(0,240,255,0.4)]"
                      : "bg-white/5 text-white/50 border-white/10 hover:bg-white/10 hover:text-white"
                  )}
                >
                  {isActive && (
                    <motion.div
                      layoutId="activeTab"
                      className="absolute inset-0 bg-primary rounded-full"
                      transition={{ type: "spring", stiffness: 400, damping: 30 }}
                    />
                  )}
                  <span className="relative z-10">{t}</span>
                </button>
              );
            })}
          </div>
        )}

        {/* ── Event Clusters ── */}
        <div className="space-y-5">
          <AnimatePresence mode="popLayout">
            {data.clusters.map((c, i) => {
              const activeGroup = c.groups?.find((g) => g.label === currentTab);
              const displayGroup = activeGroup || c.groups?.find((g) => g.label === "🌍 Global") || c.groups?.[0];
              const impact = (c.impact || "medium").toLowerCase();
              const impactInfo = IMPACT_MAP[impact] || IMPACT_MAP.medium;
              const confidence = typeof c.confidence === "number" ? c.confidence : null;

              return (
                <motion.div
                  key={`${i}-${currentTab}`}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.97 }}
                  transition={{ duration: 0.3, delay: i * 0.08 }}
                  layout
                  className="rounded-xl border border-white/10 bg-black/40 backdrop-blur-md overflow-hidden"
                >
                  {/* Left accent bar with gradient */}
                  <div className="flex">
                    <div className={cn(
                      "w-1 flex-shrink-0",
                      impact === "high" ? "bg-gradient-to-b from-red-500 to-red-700" :
                      impact === "medium" ? "bg-gradient-to-b from-amber-400 to-amber-600" :
                      "bg-gradient-to-b from-emerald-400 to-emerald-600"
                    )} />

                    <div className="flex-1 p-4 space-y-4">

                      {/* ── 🧠 Headline ── */}
                      <div>
                        <div className="flex items-center gap-1.5 text-[9px] uppercase tracking-widest font-bold text-primary/60 mb-1">
                          <Layers className="w-3 h-3" /> Headline
                        </div>
                        <h4 className="text-base font-bold text-white leading-tight">{c.event_title}</h4>
                      </div>

                      {/* ── ⚡ AI Summary ── */}
                      {c.summary && (
                        <div className="p-3 rounded-lg bg-primary/5 border border-primary/15">
                          <div className="flex items-center gap-1.5 text-[9px] uppercase tracking-widest font-bold text-primary/70 mb-1.5">
                            <Zap className="w-3 h-3" /> AI Summary
                          </div>
                          <p className="text-sm text-white/85 leading-relaxed">{c.summary}</p>
                        </div>
                      )}

                      {/* ── Confidence Score ── */}
                      {confidence !== null && <ConfidenceBar score={confidence} />}

                      {/* ── 📊 Key Facts + 🌍 Perspective (2-col grid) ── */}
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">

                        {/* Key Facts */}
                        {c.facts && c.facts.length > 0 && (
                          <div className="space-y-2 p-3 rounded-lg bg-white/4 border border-white/8">
                            <div className="flex items-center gap-1.5 text-[9px] uppercase tracking-widest font-bold text-emerald-400/80 mb-2">
                              <FileText className="w-3.5 h-3.5" /> Key Facts
                            </div>
                            <ul className="space-y-2">
                              {c.facts.map((f, j) => {
                                const isString = typeof f === "string";
                                const factText = isString ? f : f.fact;
                                const conf = isString ? null : (f.confidence || null);
                                const srcUrl = isString ? null : f.source;
                                const evCount = isString ? null : f.evidence_count;
                                return (
                                  <li key={j} className="text-sm text-white/80 flex items-start gap-2 leading-relaxed">
                                    <span className="text-emerald-500 mt-0.5 text-xs flex-shrink-0">✔</span>
                                    <div className="flex-1 min-w-0">
                                      <span>{factText}</span>
                                      {conf && (
                                        <div className="flex items-center flex-wrap gap-1.5 mt-1">
                                          <span className={cn(
                                            "text-[8px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider border",
                                            conf === "very_high" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" :
                                            conf === "high"      ? "bg-blue-500/10 text-blue-400 border-blue-500/20" :
                                            conf === "low"       ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                                                                   "bg-red-500/10 text-red-400 border-red-500/20"
                                          )}>
                                            {conf.replace("_", " ")} confidence {evCount ? `(${evCount}×)` : ""}
                                          </span>
                                          {srcUrl && (
                                            <a href={srcUrl} target="_blank" rel="noreferrer"
                                              className="text-[8px] text-primary/60 hover:text-primary flex items-center gap-0.5">
                                              <Link2 className="w-2.5 h-2.5" /> verify
                                            </a>
                                          )}
                                        </div>
                                      )}
                                    </div>
                                  </li>
                                );
                              })}
                            </ul>
                          </div>
                        )}

                        {/* Perspective */}
                        {displayGroup && (
                          <div className="space-y-2 p-3 rounded-lg bg-white/4 border border-white/8 flex flex-col justify-between">
                            <div>
                              <div className="flex items-center justify-between gap-1.5 mb-2">
                                <span className="flex items-center gap-1.5 text-[9px] uppercase tracking-widest font-bold text-cyan-400/80">
                                  <Globe2 className="w-3.5 h-3.5" /> Perspective
                                </span>
                                <div className="flex items-center gap-1 text-[8px]">
                                  {displayGroup.strength === "strong" && (
                                    <span className="flex items-center gap-1 text-emerald-400">
                                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> strong
                                    </span>
                                  )}
                                  {displayGroup.strength === "medium" && (
                                    <span className="flex items-center gap-1 text-blue-400">
                                      <div className="w-1.5 h-1.5 rounded-full bg-blue-400" /> medium
                                    </span>
                                  )}
                                  {displayGroup.strength === "weak" && (
                                    <span className="flex items-center gap-1 text-amber-400">
                                      <div className="w-1.5 h-1.5 rounded-full bg-amber-400" /> weak
                                    </span>
                                  )}
                                </div>
                              </div>
                              <p className="text-sm text-white/80 leading-relaxed italic border-l-2 border-cyan-500/30 pl-3">
                                {displayGroup.view || "No specific perspective available."}
                              </p>
                            </div>
                            {displayGroup.sources && (
                              <div className="mt-2 flex flex-wrap justify-end gap-1.5">
                                {displayGroup.sources.slice(0, 3).map((src, idx) => (
                                  <a key={idx} href={src} target="_blank" rel="noreferrer"
                                    className="inline-flex items-center gap-1 text-[8px] text-cyan-400/60 hover:text-cyan-400 border border-cyan-400/10 px-1.5 py-0.5 rounded bg-cyan-400/5">
                                    <Link2 className="w-2 h-2" /> Src {idx + 1}
                                  </a>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>

                      {/* ── 📈 Impact Score ── */}
                      <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/4 border border-white/8">
                        <div className="flex items-center gap-1.5 text-[9px] uppercase tracking-widest font-bold text-white/40">
                          <BarChart3 className="w-3 h-3" /> Impact
                        </div>
                        <div className={cn("flex items-center gap-1.5 text-xs font-bold", impactInfo.color)}>
                          <span>{impactEmoji[impact]}</span>
                          {impactInfo.icon}
                          <span>{impactInfo.label}</span>
                          {c.impact_note && (
                            <span className="text-white/40 font-normal text-[10px]">— {c.impact_note}</span>
                          )}
                        </div>
                      </div>

                      {/* ── 🧵 Timeline ── */}
                      {c.timeline && c.timeline.length > 0 && (
                        <div className="p-3 rounded-lg bg-white/4 border border-white/8">
                          <div className="flex items-center gap-1.5 text-[9px] uppercase tracking-widest font-bold text-violet-400/80 mb-3">
                            <Clock className="w-3 h-3" /> Timeline
                          </div>
                          <div className="relative pl-4">
                            {/* Vertical line */}
                            <div className="absolute left-1.5 top-0 bottom-0 w-px bg-white/10" />
                            <div className="space-y-2">
                              {c.timeline.map((entry, k) => (
                                <div key={k} className="flex items-start gap-3 relative">
                                  <div className="absolute -left-3 top-1 w-2 h-2 rounded-full bg-primary/60 border border-primary/30 flex-shrink-0" />
                                  <div>
                                    <span className="text-[9px] font-bold text-primary/60 uppercase tracking-wider">{entry.date}</span>
                                    <p className="text-xs text-white/70 leading-relaxed">{entry.event}</p>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* ── 🔗 Sources ── */}
                      {c.sources && c.sources.length > 0 && (
                        <div className="pt-2 border-t border-white/6">
                          <div className="flex items-center gap-1.5 text-[9px] uppercase tracking-widest font-bold text-white/35 mb-2">
                            <Link2 className="w-3 h-3" /> Sources
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {c.sources.map((s, j) => (
                              <a
                                key={j}
                                href={s.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white/5 border border-white/8 text-white/55 hover:text-primary hover:bg-primary/10 hover:border-primary/25 transition-all duration-200 text-xs max-w-[180px] group/src"
                              >
                                <Target className="w-3 h-3 flex-shrink-0 group-hover/src:text-primary" />
                                <span className="truncate">{s.title}</span>
                                <ChevronRight className="w-3 h-3 flex-shrink-0 group-hover/src:translate-x-0.5 transition-transform" />
                              </a>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>

        {/* Footer shimmer line */}
        <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent" />
      </div>
    </div>
  );
}
