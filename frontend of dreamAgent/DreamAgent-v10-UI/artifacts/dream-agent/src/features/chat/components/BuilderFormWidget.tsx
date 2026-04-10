import { useState } from "react";
import {
  Plus, Trash2, Globe, ShoppingBag, User, FileText, BarChart2,
  Database, ChevronRight, ChevronLeft, Rocket, Check, Loader2,
  Youtube, Instagram, Twitter, Facebook, Phone, Mail, MapPin,
  Sparkles, Zap, Code2, Shield, X,
} from "lucide-react";

// ─── Types ─────────────────────────────────────────────────────────────────────
interface Product { name: string; price: string; description: string; image: string; }
interface Social { platform: string; url: string; }
export interface BuilderPrefs {
  name: string; type: string; features: string[];
  database: { enabled: boolean; type: string };
  purpose: string; products: Product[];
  contact: { address: string; phone: string; email: string };
  socials: Social[]; footer: string; design: string;
  audience: string[]; pages: string[];
}

const SITE_TYPES = [
  { id: "ecommerce",  label: "E-Commerce", icon: ShoppingBag, col: "from-orange-500/20 border-orange-500/30" },
  { id: "portfolio",  label: "Portfolio",   icon: User,        col: "from-purple-500/20 border-purple-500/30" },
  { id: "blog",       label: "Blog",        icon: FileText,    col: "from-blue-500/20  border-blue-500/30"   },
  { id: "business",   label: "Business",    icon: Globe,       col: "from-green-500/20 border-green-500/30"  },
  { id: "saas",       label: "SaaS",        icon: BarChart2,   col: "from-cyan-500/20  border-cyan-500/30"   },
  { id: "custom",     label: "Custom",      icon: Code2,       col: "from-pink-500/20  border-pink-500/30"   },
];
const FEATURES: { id: string; label: string }[] = [
  { id: "auth",          label: "🔐 Login/Auth"     },
  { id: "payment",       label: "💳 Payment"         },
  { id: "admin",         label: "🧭 Admin Panel"     },
  { id: "search",        label: "🔍 Search"          },
  { id: "chat",          label: "💬 Chat Support"    },
  { id: "analytics",     label: "📊 Analytics"       },
  { id: "api",           label: "🔗 API Integration" },
  { id: "notifications", label: "🔔 Notifications"   },
];
const SOCIAL_PLATFORMS = [
  { id: "youtube",   label: "YouTube",     icon: Youtube   },
  { id: "instagram", label: "Instagram",   icon: Instagram },
  { id: "twitter",   label: "Twitter / X", icon: Twitter   },
  { id: "facebook",  label: "Facebook",    icon: Facebook  },
];
const DESIGN_STYLES = [
  { id: "minimal",   label: "Minimal",   desc: "Clean, whitespace-forward" },
  { id: "modern",    label: "Modern",    desc: "Bold, vibrant, dynamic"    },
  { id: "premium",   label: "Premium",   desc: "Luxury, high-end feel"     },
  { id: "dark",      label: "Dark",      desc: "Deep, dramatic, cinematic" },
  { id: "colorful",  label: "Colorful",  desc: "Vibrant, playful, energetic"},
];
const AUDIENCES = ["Kids","Students","Professionals","Businesses","Everyone"];
const PAGES_LIST = ["home","about","contact","products","blog","dashboard","pricing","terms"];
const STEPS = ["Info","Type","Features","Database","Design","Content","Review"];
const BUILD_STAGES = [
  { icon: Sparkles, text: "Analyzing your idea..."   },
  { icon: Zap,      text: "Generating structure..."  },
  { icon: Code2,    text: "Building website..."      },
  { icon: Shield,   text: "Securing your app..."     },
  { icon: Rocket,   text: "Deploying..."             },
];

function defaultPrefs(): BuilderPrefs {
  return {
    name: "", type: "", features: [],
    database: { enabled: false, type: "sqlite" },
    purpose: "", products: [{ name: "", price: "", description: "", image: "" }],
    contact: { address: "", phone: "", email: "" },
    socials: [], footer: "", design: "modern", audience: [], pages: ["home","contact"],
  };
}
function toggle<T>(arr: T[], val: T): T[] {
  return arr.includes(val) ? arr.filter(v => v !== val) : [...arr, val];
}

// ─── Tiny styled primitives ─────────────────────────────────────────────────-
const TInput = (p: React.InputHTMLAttributes<HTMLInputElement>) => (
  <input {...p} className={`w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/10 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/60 transition-all ${p.className ?? ""}`} />
);
const TTextarea = (p: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => (
  <textarea {...p} rows={3} className={`w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/10 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/60 transition-all resize-none ${p.className ?? ""}`} />
);

// ─── Main exported component ────────────────────────────────────────────────-
interface BuilderFormProps {
  onClose?: () => void;
  onSubmit?: (prefs: BuilderPrefs) => void;
}

export function BuilderFormWidget({ onClose, onSubmit }: BuilderFormProps) {
  const [step, setStep] = useState(0);
  const [prefs, setPrefs] = useState<BuilderPrefs>(defaultPrefs());
  const [customFeature, setCustomFeature] = useState("");
  const [building, setBuilding] = useState(false);
  const [buildStage, setBuildStage] = useState(0);
  const [built, setBuilt] = useState(false);
  const [error, setError] = useState("");

  const upd = (patch: Partial<BuilderPrefs>) => setPrefs(p => ({ ...p, ...patch }));

  // ─── Build submission ────────────────────────────────────────────────────
  const handleBuild = async () => {
    setBuilding(true); setError("");
    for (let i = 0; i < BUILD_STAGES.length - 1; i++) {
      await new Promise(r => setTimeout(r, 1100));
      setBuildStage(i + 1);
    }
    try {
      const payload = {
        ...prefs,
        name: prefs.name || "Untitled",
        type: prefs.type || "landing",
        backend: prefs.database.enabled,
        products: prefs.type === "ecommerce" ? prefs.products : [],
      };
      const res = await fetch("/api/v1/builder/build", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || "Build failed");
      }
      setBuilt(true);
      await new Promise(r => setTimeout(r, 1200));
      onSubmit?.(prefs);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setBuilding(false);
    }
  };

  // ─── Build progress overlay ──────────────────────────────────────────────
  if (building) {
    const Stage = BUILD_STAGES[buildStage];
    const progress = built ? 100 : ((buildStage + 1) / BUILD_STAGES.length) * 90;
    return (
      <div className="rounded-2xl border border-primary/20 bg-black/60 backdrop-blur-xl p-6 shadow-2xl shadow-primary/10 text-center space-y-5 my-2">
        <div className="relative mx-auto w-16 h-16">
          <div className="absolute inset-0 rounded-full border-2 border-primary/20 animate-ping" />
          <div className="absolute inset-1 rounded-full border-2 border-primary/40 animate-spin" style={{ animationDuration: "3s" }} />
          <div className="absolute inset-0 rounded-full bg-primary/10 flex items-center justify-center">
            {built ? <Rocket className="w-8 h-8 text-primary animate-bounce" /> : <Stage.icon className="w-8 h-8 text-primary" />}
          </div>
        </div>
        <div>
          <p className="font-display font-bold text-foreground">{built ? "🚀 Site Built!" : "Building your website..."}</p>
          <p className="text-xs text-muted-foreground mt-1">{built ? "Opening builder panel..." : Stage.text}</p>
        </div>
        <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
          <div className="h-full bg-gradient-to-r from-primary to-secondary rounded-full transition-all duration-1000" style={{ width: `${progress}%` }} />
        </div>
        <div className="flex flex-wrap justify-center gap-1.5">
          {BUILD_STAGES.map((s, i) => (
            <span key={i} className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-semibold border transition-all ${
              i < buildStage ? "bg-emerald-500/20 border-emerald-500/30 text-emerald-400"
              : i === buildStage ? "bg-primary/20 border-primary/40 text-primary"
              : "border-white/10 text-white/20"}`}>
              {i < buildStage ? <Check className="w-2.5 h-2.5" /> : <s.icon className="w-2.5 h-2.5" />}
              {s.text.replace("...", "")}
            </span>
          ))}
        </div>
        {error && <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs">{error}</div>}
      </div>
    );
  }

  // ─── Step panels ─────────────────────────────────────────────────────────
  const panels = [
    /* 0 – Info */
    <div key="0" className="space-y-4">
      <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest block">Website Name (optional)</label>
      <TInput placeholder="Enter your website name..." value={prefs.name} onChange={e => upd({ name: e.target.value })} />
      <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest block mt-3">Purpose / Goal</label>
      <TTextarea placeholder="Example: Selling chocolates, online store, portfolio showcase..." value={prefs.purpose} onChange={e => upd({ purpose: e.target.value })} />
    </div>,

    /* 1 – Type */
    <div key="1">
      <div className="grid grid-cols-3 gap-2">
        {SITE_TYPES.map(t => (
          <button key={t.id} onClick={() => upd({ type: t.id })}
            className={`relative p-3 rounded-2xl border bg-gradient-to-br text-left transition-all hover:scale-[1.02] ${prefs.type === t.id ? t.col + " ring-2 ring-primary/30" : "border-white/10 from-white/5 to-transparent hover:border-white/20"}`}>
            <t.icon className={`w-5 h-5 mb-1.5 ${prefs.type === t.id ? "text-primary" : "text-muted-foreground"}`} />
            <div className="text-xs font-semibold text-foreground">{t.label}</div>
            {prefs.type === t.id && <div className="absolute top-1.5 right-1.5 w-4 h-4 rounded-full bg-primary flex items-center justify-center"><Check className="w-2.5 h-2.5 text-black" /></div>}
          </button>
        ))}
      </div>
    </div>,

    /* 2 – Features + Pages */
    <div key="2" className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {FEATURES.map(f => (
          <button key={f.id} onClick={() => upd({ features: toggle(prefs.features, f.id) })}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${prefs.features.includes(f.id) ? "bg-primary/20 border-primary/50 text-primary" : "border-white/10 text-muted-foreground hover:border-white/25 hover:bg-white/5"}`}>
            {f.label}
          </button>
        ))}
        {prefs.features.filter(f => !FEATURES.find(ff => ff.id === f)).map(f => (
          <span key={f} className="flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium bg-secondary/20 border border-secondary/40 text-secondary">
            ✨ {f}
            <button onClick={() => upd({ features: prefs.features.filter(ff => ff !== f) })}><X className="w-3 h-3" /></button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <TInput placeholder="Add custom feature..." value={customFeature}
          onChange={e => setCustomFeature(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && customFeature.trim()) { const id = customFeature.trim().toLowerCase().replace(/\s+/g, "-"); if (!prefs.features.includes(id)) upd({ features: [...prefs.features, id] }); setCustomFeature(""); }}} />
        <button onClick={() => { if (!customFeature.trim()) return; const id = customFeature.trim().toLowerCase().replace(/\s+/g, "-"); if (!prefs.features.includes(id)) upd({ features: [...prefs.features, id] }); setCustomFeature(""); }}
          className="px-3 py-2 rounded-xl bg-primary/10 border border-primary/30 text-primary hover:bg-primary/20 transition-all shrink-0"><Plus className="w-4 h-4" /></button>
      </div>
      <div>
        <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest block mb-2">Pages</label>
        <div className="flex flex-wrap gap-1.5">
          {PAGES_LIST.map(pg => (
            <button key={pg} onClick={() => upd({ pages: toggle(prefs.pages, pg) })}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-bold border capitalize transition-all ${prefs.pages.includes(pg) ? "bg-secondary/20 border-secondary/40 text-secondary" : "border-white/10 text-muted-foreground hover:border-white/25 hover:bg-white/5"}`}>
              {pg}
            </button>
          ))}
        </div>
      </div>
    </div>,

    /* 3 – Database */
    <div key="3" className="space-y-4">
      <div className="flex gap-3">
        {[true, false].map(val => (
          <button key={String(val)} onClick={() => upd({ database: { ...prefs.database, enabled: val } })}
            className={`flex-1 py-3 rounded-2xl border text-sm font-semibold transition-all ${prefs.database.enabled === val ? "bg-primary/15 border-primary/50 text-primary" : "border-white/10 text-muted-foreground hover:border-white/20 hover:bg-white/5"}`}>
            {val ? "✅ Yes, I need a database" : "⚡ No, static site"}
          </button>
        ))}
      </div>
      {prefs.database.enabled && (
        <div className="grid grid-cols-3 gap-2">
          {[
            { id: "sqlite",     label: "SQLite",     badge: "Default"      },
            { id: "postgresql", label: "PostgreSQL",  badge: "Recommended"  },
            { id: "mongodb",    label: "MongoDB",     badge: "NoSQL"        },
          ].map(db => (
            <button key={db.id} onClick={() => upd({ database: { enabled: true, type: db.id } })}
              className={`p-3 rounded-2xl border text-left transition-all hover:scale-[1.02] ${prefs.database.type === db.id ? "bg-primary/10 border-primary/50" : "border-white/10 bg-white/3 hover:border-white/20"}`}>
              <div className="text-[9px] text-muted-foreground font-bold tracking-widest uppercase mb-0.5">{db.badge}</div>
              <div className="text-sm font-bold text-foreground">{db.label}</div>
              {prefs.database.type === db.id && <div className="mt-2 w-full h-0.5 bg-primary rounded-full" />}
            </button>
          ))}
        </div>
      )}
    </div>,

    /* 4 – Design + Audience */
    <div key="4" className="space-y-4">
      <div>
        <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest block mb-2">Design Style</label>
        <div className="grid grid-cols-5 gap-1.5">
          {DESIGN_STYLES.map(ds => (
            <button key={ds.id} onClick={() => upd({ design: ds.id })}
              className={`p-2 rounded-xl border text-center transition-all hover:scale-[1.02] ${prefs.design === ds.id ? "bg-secondary/15 border-secondary/50 text-secondary" : "border-white/10 text-muted-foreground hover:border-white/20"}`}>
              <div className="text-xs font-bold">{ds.label}</div>
              <div className="text-[9px] opacity-60 mt-0.5 leading-tight">{ds.desc}</div>
            </button>
          ))}
        </div>
      </div>
      <div>
        <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest block mb-2">Target Audience</label>
        <div className="flex flex-wrap gap-2">
          {AUDIENCES.map(a => (
            <button key={a} onClick={() => upd({ audience: toggle(prefs.audience, a) })}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${prefs.audience.includes(a) ? "bg-secondary/20 border-secondary/40 text-secondary" : "border-white/10 text-muted-foreground hover:border-white/25 hover:bg-white/5"}`}>
              {a}
            </button>
          ))}
        </div>
      </div>
    </div>,

    /* 5 – Content */
    <div key="5" className="space-y-5">
      {prefs.type === "ecommerce" && (
        <div>
          <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest block mb-2">🛍️ Products</label>
          <div className="space-y-3">
            {prefs.products.map((p, i) => (
              <div key={i} className="p-3 rounded-2xl border border-white/10 bg-white/3 space-y-2 relative">
                <button onClick={() => upd({ products: prefs.products.filter((_, ii) => ii !== i) })}
                  className="absolute top-2 right-2 w-6 h-6 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 flex items-center justify-center hover:bg-red-500/20 transition-all">
                  <Trash2 className="w-3 h-3" />
                </button>
                <div className="grid grid-cols-2 gap-2">
                  <TInput placeholder="Product name" value={p.name} onChange={e => { const ps = [...prefs.products]; ps[i].name = e.target.value; upd({ products: ps }); }} />
                  <TInput placeholder="Price" value={p.price} onChange={e => { const ps = [...prefs.products]; ps[i].price = e.target.value; upd({ products: ps }); }} />
                </div>
                <TInput placeholder="Description" value={p.description} onChange={e => { const ps = [...prefs.products]; ps[i].description = e.target.value; upd({ products: ps }); }} />
                <TInput placeholder="Image URL (optional)" value={p.image} onChange={e => { const ps = [...prefs.products]; ps[i].image = e.target.value; upd({ products: ps }); }} />
              </div>
            ))}
            <button onClick={() => upd({ products: [...prefs.products, { name: "", price: "", description: "", image: "" }] })}
              className="w-full py-2.5 rounded-xl border border-dashed border-white/20 text-muted-foreground hover:border-primary/40 hover:text-primary transition-all flex items-center justify-center gap-2 text-xs">
              <Plus className="w-3.5 h-3.5" /> Add Product
            </button>
          </div>
        </div>
      )}
      <div>
        <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest block mb-2">📞 Contact</label>
        <div className="space-y-2">
          <div className="flex items-center gap-2"><MapPin className="w-4 h-4 text-muted-foreground shrink-0" /><TInput placeholder="Address" value={prefs.contact.address} onChange={e => upd({ contact: { ...prefs.contact, address: e.target.value } })} /></div>
          <div className="flex items-center gap-2"><Phone className="w-4 h-4 text-muted-foreground shrink-0" /><TInput placeholder="Phone" value={prefs.contact.phone} onChange={e => upd({ contact: { ...prefs.contact, phone: e.target.value } })} /></div>
          <div className="flex items-center gap-2"><Mail className="w-4 h-4 text-muted-foreground shrink-0" /><TInput placeholder="Email" value={prefs.contact.email} onChange={e => upd({ contact: { ...prefs.contact, email: e.target.value } })} /></div>
        </div>
      </div>
      <div>
        <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest block mb-2">🌐 Social Media</label>
        <div className="space-y-2">
          {prefs.socials.map((s, i) => (
            <div key={i} className="flex items-center gap-2">
              <select value={s.platform} onChange={e => { const ss = [...prefs.socials]; ss[i].platform = e.target.value; upd({ socials: ss }); }}
                className="px-2 py-2.5 rounded-xl bg-white/5 border border-white/10 text-foreground text-xs focus:outline-none focus:border-primary/60 shrink-0">
                {SOCIAL_PLATFORMS.map(sp => <option key={sp.id} value={sp.id}>{sp.label}</option>)}
              </select>
              <TInput placeholder="URL" value={s.url} onChange={e => { const ss = [...prefs.socials]; ss[i].url = e.target.value; upd({ socials: ss }); }} />
              <button onClick={() => upd({ socials: prefs.socials.filter((_, ii) => ii !== i) })} className="w-9 h-9 shrink-0 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 flex items-center justify-center hover:bg-red-500/20 transition-all"><Trash2 className="w-3.5 h-3.5" /></button>
            </div>
          ))}
          <button onClick={() => upd({ socials: [...prefs.socials, { platform: "instagram", url: "" }] })}
            className="w-full py-2 rounded-xl border border-dashed border-white/20 text-muted-foreground hover:border-primary/40 hover:text-primary transition-all flex items-center justify-center gap-1.5 text-xs">
            <Plus className="w-3.5 h-3.5" /> Add Social Media
          </button>
        </div>
      </div>
      <div>
        <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest block mb-2">📄 Footer</label>
        <TTextarea placeholder={`© 2026 ${prefs.name || "MyBrand"}. All rights reserved.`} value={prefs.footer} onChange={e => upd({ footer: e.target.value })} />
      </div>
    </div>,

    /* 6 – Review */
    <div key="6">
      <div className="bg-black/50 rounded-2xl border border-white/10 overflow-hidden">
        <div className="px-4 py-2.5 border-b border-white/8 flex items-center gap-2 bg-white/3">
          <Code2 className="w-3.5 h-3.5 text-primary" />
          <span className="text-[10px] font-mono text-muted-foreground">preferences.json</span>
        </div>
        <pre className="p-4 text-[10px] font-mono text-green-400/90 overflow-x-auto max-h-56 leading-relaxed">
          {JSON.stringify({
            name: prefs.name || "Untitled", type: prefs.type || "landing",
            features: prefs.features, database: prefs.database,
            purpose: prefs.purpose,
            products: prefs.type === "ecommerce" ? prefs.products : undefined,
            contact: prefs.contact, socials: prefs.socials,
            footer: prefs.footer, design: prefs.design,
            audience: prefs.audience, pages: prefs.pages,
          }, null, 2)}
        </pre>
      </div>
    </div>,
  ];

  return (
    <div className="my-2 rounded-2xl border border-primary/20 bg-black/60 backdrop-blur-xl shadow-2xl shadow-primary/10 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/8 bg-gradient-to-r from-primary/10 to-secondary/5">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-primary/20 border border-primary/30 flex items-center justify-center">
            <Globe className="w-4 h-4 text-primary" />
          </div>
          <div>
            <div className="font-display font-bold text-foreground text-sm">Website Builder</div>
            <div className="text-[10px] text-muted-foreground">Configure your project</div>
          </div>
        </div>
        {onClose && (
          <button onClick={onClose} className="w-7 h-7 rounded-lg bg-white/5 border border-white/10 text-muted-foreground hover:text-foreground hover:bg-white/10 flex items-center justify-center transition-all">
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Step pills */}
      <div className="flex items-center gap-1 px-5 py-3 border-b border-white/5 overflow-x-auto">
        {STEPS.map((s, i) => (
          <div key={s} className="flex items-center gap-1 shrink-0">
            <button onClick={() => i < step && setStep(i)}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold transition-all ${
                i === step ? "bg-primary text-black shadow-[0_0_8px_rgba(0,235,255,0.4)]"
                : i < step ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 cursor-pointer"
                : "bg-white/5 text-muted-foreground border border-white/10"}`}>
              {i < step ? <Check className="w-2.5 h-2.5" /> : <span>{i + 1}</span>} {s}
            </button>
            {i < STEPS.length - 1 && <div className={`w-3 h-px rounded-full ${i < step ? "bg-emerald-500/50" : "bg-white/10"}`} />}
          </div>
        ))}
      </div>

      {/* Panel content */}
      <div className="px-5 py-5">{panels[step]}</div>

      {/* Navigation */}
      <div className="flex items-center justify-between px-5 pb-5 pt-0">
        <button onClick={() => setStep(s => Math.max(0, s - 1))} disabled={step === 0}
          className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl border border-white/10 text-muted-foreground hover:text-foreground hover:border-white/25 hover:bg-white/5 transition-all disabled:opacity-30 text-xs font-semibold">
          <ChevronLeft className="w-3.5 h-3.5" /> Back
        </button>
        {step < STEPS.length - 1 ? (
          <button onClick={() => setStep(s => s + 1)}
            className="flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-primary/10 border border-primary/40 text-primary hover:bg-primary hover:text-black font-bold text-xs transition-all duration-300">
            Next <ChevronRight className="w-3.5 h-3.5" />
          </button>
        ) : (
          <button onClick={handleBuild} disabled={building}
            className="flex items-center gap-1.5 px-6 py-2.5 rounded-xl bg-gradient-to-r from-primary to-secondary text-black font-bold text-xs transition-all duration-300 shadow-lg shadow-primary/20 hover:shadow-primary/40 hover:scale-[1.02] disabled:opacity-50">
            <Rocket className="w-3.5 h-3.5" /> Build My Website
          </button>
        )}
      </div>
    </div>
  );
}
