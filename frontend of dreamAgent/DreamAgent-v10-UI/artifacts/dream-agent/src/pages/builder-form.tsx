import { useState } from "react";
import { useLocation } from "wouter";
import { Layout } from "@/components/layout";
import {
  Plus, Trash2, Globe, ShoppingBag, User, FileText, BarChart2,
  Database, ChevronRight, ChevronLeft, Rocket, Check, Loader2,
  Youtube, Instagram, Twitter, Facebook, Phone, Mail, MapPin,
  Sparkles, Zap, Code2, Shield
} from "lucide-react";

// ─── Types ──────────────────────────────────────────────────────────────────
interface Product { name: string; price: string; description: string; image: string; }
interface Social { platform: string; url: string; }
interface BuilderPrefs {
  name: string;
  type: string;
  features: string[];
  database: { enabled: boolean; type: string };
  purpose: string;
  products: Product[];
  contact: { address: string; phone: string; email: string };
  socials: Social[];
  footer: string;
  design: string;
  audience: string[];
  pages: string[];
}

const SITE_TYPES = [
  { id: "ecommerce", label: "E-Commerce", icon: ShoppingBag, color: "from-orange-500/20 to-orange-500/5 border-orange-500/30" },
  { id: "portfolio", label: "Portfolio", icon: User, color: "from-purple-500/20 to-purple-500/5 border-purple-500/30" },
  { id: "blog", label: "Blog", icon: FileText, color: "from-blue-500/20 to-blue-500/5 border-blue-500/30" },
  { id: "business", label: "Business", icon: Globe, color: "from-green-500/20 to-green-500/5 border-green-500/30" },
  { id: "saas", label: "SaaS", icon: BarChart2, color: "from-cyan-500/20 to-cyan-500/5 border-cyan-500/30" },
  { id: "custom", label: "Custom", icon: Code2, color: "from-pink-500/20 to-pink-500/5 border-pink-500/30" },
];
const FEATURES = ["auth", "payment", "admin", "search", "chat", "analytics", "api", "notifications", "dark-mode"];
const FEATURE_LABELS: Record<string, string> = {
  auth: "🔐 Login/Auth", payment: "💳 Payment", admin: "🧭 Admin Panel",
  search: "🔍 Search", chat: "💬 Chat Support", analytics: "📊 Analytics",
  api: "🔗 API Integration", notifications: "🔔 Notifications", "dark-mode": "🌙 Dark Mode"
};
const SOCIAL_PLATFORMS = [
  { id: "youtube", label: "YouTube", icon: Youtube, color: "text-red-500" },
  { id: "instagram", label: "Instagram", icon: Instagram, color: "text-pink-500" },
  { id: "twitter", label: "Twitter / X", icon: Twitter, color: "text-sky-400" },
  { id: "facebook", label: "Facebook", icon: Facebook, color: "text-blue-500" },
];
const DESIGN_STYLES = [
  { id: "minimal", label: "Minimal", desc: "Clean, whitespace-forward" },
  { id: "modern", label: "Modern", desc: "Bold, vibrant, dynamic" },
  { id: "premium", label: "Premium", desc: "Luxury, high-end feel" },
  { id: "dark", label: "Dark", desc: "Deep, dramatic, cinematic" },
  { id: "colorful", label: "Colorful", desc: "Vibrant, playful, energetic" },
];
const AUDIENCES = ["Kids", "Students", "Professionals", "Businesses", "Everyone"];
const PAGES_LIST = ["home", "about", "contact", "products", "blog", "dashboard", "pricing", "terms"];

const STEPS = ["Info", "Type", "Features", "Database", "Design", "Content", "Review"];
const BUILD_STAGES = [
  { icon: Sparkles, text: "Analyzing your idea..." },
  { icon: Zap, text: "Generating structure..." },
  { icon: Code2, text: "Building website..." },
  { icon: Shield, text: "Securing your app..." },
  { icon: Rocket, text: "Deploying..." },
];

const defaultPrefs = (): BuilderPrefs => ({
  name: "", type: "", features: [],
  database: { enabled: false, type: "sqlite" },
  purpose: "",
  products: [{ name: "", price: "", description: "", image: "" }],
  contact: { address: "", phone: "", email: "" },
  socials: [],
  footer: "",
  design: "modern",
  audience: [],
  pages: ["home", "contact"],
});

// ─── Toggle helper ────────────────────────────────────────────────────────────
function toggle<T>(arr: T[], val: T): T[] {
  return arr.includes(val) ? arr.filter(v => v !== val) : [...arr, val];
}

// ─── Styled primitives ────────────────────────────────────────────────────────
const Input = ({ className = "", ...p }: React.InputHTMLAttributes<HTMLInputElement>) => (
  <input
    className={`w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/60 focus:bg-white/8 transition-all text-sm ${className}`}
    {...p}
  />
);
const Textarea = ({ className = "", ...p }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => (
  <textarea
    className={`w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/60 transition-all text-sm resize-none ${className}`}
    rows={3}
    {...p}
  />
);
const SectionTitle = ({ icon: Icon, label, sub }: { icon: React.ElementType; label: string; sub?: string }) => (
  <div className="flex items-center gap-3 mb-6">
    <div className="w-10 h-10 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0">
      <Icon className="w-5 h-5" />
    </div>
    <div>
      <h2 className="font-display font-bold text-foreground text-lg leading-tight">{label}</h2>
      {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  </div>
);

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function BuilderForm() {
  const [, setLocation] = useLocation();
  const [step, setStep] = useState(0);
  const [prefs, setPrefs] = useState<BuilderPrefs>(defaultPrefs());
  const [customFeature, setCustomFeature] = useState("");
  const [building, setBuilding] = useState(false);
  const [buildStage, setBuildStage] = useState(0);
  const [built, setBuilt] = useState(false);
  const [error, setError] = useState("");

  const update = (patch: Partial<BuilderPrefs>) => setPrefs(p => ({ ...p, ...patch }));

  // ─── Steps ────────────────────────────────────────────────────────
  const steps = [
    // 0 – Basic Info
    <div key="0" className="space-y-5">
      <SectionTitle icon={Globe} label="Basic Info" sub="Give your website a name and purpose" />
      <div>
        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-2 block">Website Name (Optional)</label>
        <Input placeholder="Enter your website name..." value={prefs.name} onChange={e => update({ name: e.target.value })} />
      </div>
      <div>
        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-2 block">Purpose / Goal</label>
        <Textarea
          placeholder="Example: Selling chocolates, online store, portfolio showcase..."
          value={prefs.purpose}
          onChange={e => update({ purpose: e.target.value })}
        />
      </div>
    </div>,

    // 1 – Website Type
    <div key="1" className="space-y-4">
      <SectionTitle icon={Globe} label="Website Type" sub="What kind of site are you building?" />
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {SITE_TYPES.map(t => (
          <button
            key={t.id}
            onClick={() => update({ type: t.id })}
            className={`relative p-4 rounded-2xl border bg-gradient-to-br text-left transition-all duration-300 group hover:scale-[1.02] ${
              prefs.type === t.id
                ? t.color + " ring-2 ring-primary/40 shadow-lg shadow-primary/10"
                : "border-white/10 from-white/5 to-transparent hover:border-white/20"
            }`}
          >
            <t.icon className={`w-6 h-6 mb-2 transition-colors ${prefs.type === t.id ? "text-primary" : "text-muted-foreground group-hover:text-foreground"}`} />
            <div className="font-semibold text-sm text-foreground">{t.label}</div>
            {prefs.type === t.id && (
              <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-primary flex items-center justify-center">
                <Check className="w-3 h-3 text-black" />
              </div>
            )}
          </button>
        ))}
      </div>
    </div>,

    // 2 – Features
    <div key="2" className="space-y-5">
      <SectionTitle icon={Zap} label="Features" sub="Select all features you need" />
      <div className="flex flex-wrap gap-2">
        {FEATURES.map(f => (
          <button
            key={f}
            onClick={() => update({ features: toggle(prefs.features, f) })}
            className={`px-4 py-2 rounded-full text-sm font-medium border transition-all duration-200 ${
              prefs.features.includes(f)
                ? "bg-primary/20 border-primary/50 text-primary shadow-[0_0_12px_rgba(0,235,255,0.2)]"
                : "border-white/10 text-muted-foreground hover:border-white/25 hover:text-foreground hover:bg-white/5"
            }`}
          >
            {FEATURE_LABELS[f]}
          </button>
        ))}
      </div>
      {/* Custom feature input */}
      <div className="flex gap-2">
        <Input
          placeholder="Add custom feature..."
          value={customFeature}
          onChange={e => setCustomFeature(e.target.value)}
          onKeyDown={e => {
            if (e.key === "Enter" && customFeature.trim()) {
              const id = customFeature.trim().toLowerCase().replace(/\s+/g, "-");
              if (!prefs.features.includes(id)) update({ features: [...prefs.features, id] });
              setCustomFeature("");
            }
          }}
        />
        <button
          onClick={() => {
            if (!customFeature.trim()) return;
            const id = customFeature.trim().toLowerCase().replace(/\s+/g, "-");
            if (!prefs.features.includes(id)) update({ features: [...prefs.features, id] });
            setCustomFeature("");
          }}
          className="px-4 py-2 rounded-xl bg-primary/10 border border-primary/30 text-primary hover:bg-primary/20 transition-all shrink-0"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>
      {/* Pages selection */}
      <div>
        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-3 block">Pages to Include</label>
        <div className="flex flex-wrap gap-2">
          {PAGES_LIST.map(pg => (
            <button
              key={pg}
              onClick={() => update({ pages: toggle(prefs.pages, pg) })}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border capitalize transition-all ${
                prefs.pages.includes(pg)
                  ? "bg-secondary/20 border-secondary/50 text-secondary"
                  : "border-white/10 text-muted-foreground hover:border-white/25 hover:bg-white/5"
              }`}
            >
              {pg}
            </button>
          ))}
        </div>
      </div>
    </div>,

    // 3 – Database
    <div key="3" className="space-y-5">
      <SectionTitle icon={Database} label="Database" sub="Do you need persistent data storage?" />
      <div className="flex gap-3">
        {[true, false].map(val => (
          <button
            key={String(val)}
            onClick={() => update({ database: { ...prefs.database, enabled: val } })}
            className={`flex-1 py-4 rounded-2xl border font-semibold text-sm transition-all duration-200 ${
              prefs.database.enabled === val
                ? "bg-primary/15 border-primary/50 text-primary shadow-[0_0_16px_rgba(0,235,255,0.15)]"
                : "border-white/10 text-muted-foreground hover:border-white/20 hover:bg-white/5"
            }`}
          >
            {val ? "✅ Yes, I need a database" : "⚡ No, static site"}
          </button>
        ))}
      </div>
      {prefs.database.enabled && (
        <div className="grid grid-cols-3 gap-3 animate-fade-in-up">
          {[
            { id: "sqlite", label: "SQLite", desc: "Simple, file-based", badge: "Default" },
            { id: "postgresql", label: "PostgreSQL", desc: "Powerful, relational", badge: "Recommended" },
            { id: "mongodb", label: "MongoDB", desc: "Flexible, document", badge: "NoSQL" },
          ].map(db => (
            <button
              key={db.id}
              onClick={() => update({ database: { enabled: true, type: db.id } })}
              className={`p-4 rounded-2xl border text-left transition-all duration-200 hover:scale-[1.02] ${
                prefs.database.type === db.id
                  ? "bg-primary/10 border-primary/50 shadow-lg shadow-primary/10"
                  : "border-white/10 bg-white/3 hover:border-white/20"
              }`}
            >
              <div className="text-xs font-bold text-muted-foreground uppercase tracking-widest mb-1">{db.badge}</div>
              <div className="font-bold text-foreground">{db.label}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{db.desc}</div>
              {prefs.database.type === db.id && <div className="mt-2 w-full h-0.5 bg-primary rounded-full" />}
            </button>
          ))}
        </div>
      )}
    </div>,

    // 4 – Design + Audience
    <div key="4" className="space-y-6">
      <SectionTitle icon={Sparkles} label="Design & Audience" sub="Define the look and who you're targeting" />
      <div>
        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-3 block">Design Style</label>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {DESIGN_STYLES.map(ds => (
            <button
              key={ds.id}
              onClick={() => update({ design: ds.id })}
              className={`p-3 rounded-2xl border text-center transition-all duration-200 hover:scale-[1.02] ${
                prefs.design === ds.id
                  ? "bg-secondary/15 border-secondary/50 text-secondary shadow-[0_0_12px_rgba(139,92,246,0.15)]"
                  : "border-white/10 text-muted-foreground bg-white/3 hover:border-white/20"
              }`}
            >
              <div className="font-bold text-sm">{ds.label}</div>
              <div className="text-[10px] mt-0.5 opacity-70">{ds.desc}</div>
            </button>
          ))}
        </div>
      </div>
      <div>
        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-3 block">Target Audience</label>
        <div className="flex flex-wrap gap-2">
          {AUDIENCES.map(a => (
            <button
              key={a}
              onClick={() => update({ audience: toggle(prefs.audience, a) })}
              className={`px-4 py-2 rounded-full text-sm font-medium border transition-all ${
                prefs.audience.includes(a)
                  ? "bg-secondary/20 border-secondary/50 text-secondary"
                  : "border-white/10 text-muted-foreground hover:border-white/25 hover:bg-white/5"
              }`}
            >
              {a}
            </button>
          ))}
        </div>
      </div>
    </div>,

    // 5 – Content (products, contact, social, footer)
    <div key="5" className="space-y-8">
      <SectionTitle icon={FileText} label="Content" sub="Products, contact info, and social links" />

      {/* Products (only for ecommerce) */}
      {prefs.type === "ecommerce" && (
        <div>
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-3 block">🛍️ Products</label>
          <div className="space-y-4">
            {prefs.products.map((p, i) => (
              <div key={i} className="p-4 rounded-2xl border border-white/10 bg-white/3 space-y-3 relative">
                <button
                  onClick={() => update({ products: prefs.products.filter((_, ii) => ii !== i) })}
                  className="absolute top-3 right-3 w-7 h-7 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 flex items-center justify-center hover:bg-red-500/20 transition-all"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
                <div className="grid grid-cols-2 gap-3">
                  <Input placeholder="Product name" value={p.name} onChange={e => { const ps = [...prefs.products]; ps[i].name = e.target.value; update({ products: ps }); }} />
                  <Input placeholder="Price (e.g. 100)" value={p.price} onChange={e => { const ps = [...prefs.products]; ps[i].price = e.target.value; update({ products: ps }); }} />
                </div>
                <Input placeholder="Description" value={p.description} onChange={e => { const ps = [...prefs.products]; ps[i].description = e.target.value; update({ products: ps }); }} />
                <Input placeholder="Image URL (optional)" value={p.image} onChange={e => { const ps = [...prefs.products]; ps[i].image = e.target.value; update({ products: ps }); }} />
              </div>
            ))}
            <button
              onClick={() => update({ products: [...prefs.products, { name: "", price: "", description: "", image: "" }] })}
              className="w-full py-3 rounded-2xl border border-dashed border-white/20 text-muted-foreground hover:border-primary/40 hover:text-primary transition-all flex items-center justify-center gap-2 text-sm"
            >
              <Plus className="w-4 h-4" /> Add Product
            </button>
          </div>
        </div>
      )}

      {/* Contact */}
      <div>
        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-3 block">📞 Contact Information</label>
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <MapPin className="w-4 h-4 text-muted-foreground shrink-0" />
            <Input placeholder="Address" value={prefs.contact.address} onChange={e => update({ contact: { ...prefs.contact, address: e.target.value } })} />
          </div>
          <div className="flex items-center gap-2">
            <Phone className="w-4 h-4 text-muted-foreground shrink-0" />
            <Input placeholder="Phone number" value={prefs.contact.phone} onChange={e => update({ contact: { ...prefs.contact, phone: e.target.value } })} />
          </div>
          <div className="flex items-center gap-2">
            <Mail className="w-4 h-4 text-muted-foreground shrink-0" />
            <Input placeholder="Email address" value={prefs.contact.email} onChange={e => update({ contact: { ...prefs.contact, email: e.target.value } })} />
          </div>
        </div>
      </div>

      {/* Social Media */}
      <div>
        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-3 block">🌐 Social Media</label>
        <div className="space-y-3">
          {prefs.socials.map((s, i) => {
            const plat = SOCIAL_PLATFORMS.find(sp => sp.id === s.platform);
            return (
              <div key={i} className="flex items-center gap-2">
                <select
                  value={s.platform}
                  onChange={e => { const ss = [...prefs.socials]; ss[i].platform = e.target.value; update({ socials: ss }); }}
                  className="px-3 py-3 rounded-xl bg-white/5 border border-white/10 text-foreground text-sm focus:outline-none focus:border-primary/60 shrink-0"
                >
                  {SOCIAL_PLATFORMS.map(sp => <option key={sp.id} value={sp.id}>{sp.label}</option>)}
                </select>
                <Input placeholder={`${plat?.label ?? "Platform"} URL`} value={s.url} onChange={e => { const ss = [...prefs.socials]; ss[i].url = e.target.value; update({ socials: ss }); }} />
                <button onClick={() => update({ socials: prefs.socials.filter((_, ii) => ii !== i) })} className="w-10 h-10 shrink-0 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 flex items-center justify-center hover:bg-red-500/20 transition-all">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            );
          })}
          <button
            onClick={() => update({ socials: [...prefs.socials, { platform: "instagram", url: "" }] })}
            className="w-full py-3 rounded-2xl border border-dashed border-white/20 text-muted-foreground hover:border-primary/40 hover:text-primary transition-all flex items-center justify-center gap-2 text-sm"
          >
            <Plus className="w-4 h-4" /> Add Social Media
          </button>
        </div>
      </div>

      {/* Footer */}
      <div>
        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-2 block">📄 Footer Content</label>
        <Textarea
          placeholder={`Copyright, tagline, extra info...\nExample: © 2026 ${prefs.name || "MyBrand"}. All rights reserved.`}
          value={prefs.footer}
          onChange={e => update({ footer: e.target.value })}
        />
      </div>
    </div>,

    // 6 – Review
    <div key="6" className="space-y-5">
      <SectionTitle icon={Check} label="Review & Launch" sub="Confirm your configuration before building" />
      <div className="bg-black/40 rounded-2xl border border-white/10 overflow-hidden">
        <div className="px-5 py-3 border-b border-white/8 flex items-center gap-2">
          <Code2 className="w-4 h-4 text-primary" />
          <span className="text-xs font-mono text-muted-foreground">preferences.json</span>
        </div>
        <pre className="p-5 text-xs font-mono text-green-400/90 overflow-x-auto max-h-80 leading-relaxed">
          {JSON.stringify({
            name: prefs.name || "Untitled",
            type: prefs.type || "landing",
            features: prefs.features,
            database: prefs.database,
            purpose: prefs.purpose,
            products: prefs.type === "ecommerce" ? prefs.products : undefined,
            contact: prefs.contact,
            socials: prefs.socials,
            footer: prefs.footer,
            design: prefs.design,
            audience: prefs.audience,
            pages: prefs.pages,
          }, null, 2)}
        </pre>
      </div>
    </div>,
  ];

  // ─── Build submission ────────────────────────────────────────────────────
  const handleBuild = async () => {
    setBuilding(true);
    setError("");
    setBuildStage(0);

    // Animate stages
    for (let i = 0; i < BUILD_STAGES.length - 1; i++) {
      await new Promise(r => setTimeout(r, 1200));
      setBuildStage(i + 1);
    }

    try {
      const payload = {
        name: prefs.name || "Untitled",
        type: prefs.type || "landing",
        features: prefs.features,
        database: prefs.database,
        purpose: prefs.purpose,
        products: prefs.type === "ecommerce" ? prefs.products : [],
        contact: prefs.contact,
        socials: prefs.socials,
        footer: prefs.footer,
        design: prefs.design,
        audience: prefs.audience,
        pages: prefs.pages,
        backend: prefs.database.enabled,
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
      await new Promise(r => setTimeout(r, 1500));
      setLocation("/builder");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setBuilding(false);
    }
  };

  // ─── Build progress overlay ──────────────────────────────────────────────
  if (building) {
    const Stage = BUILD_STAGES[buildStage];
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-8">
        <div className="text-center max-w-md w-full">
          <div className="relative mx-auto w-28 h-28 mb-8">
            {/* Outer ring */}
            <div className="absolute inset-0 rounded-full border-2 border-primary/20 animate-ping" />
            <div className="absolute inset-2 rounded-full border-2 border-primary/40 animate-spin" style={{ animationDuration: "3s" }} />
            <div className="absolute inset-0 rounded-full bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center">
              {built ? (
                <Rocket className="w-12 h-12 text-primary animate-bounce" />
              ) : (
                <Stage.icon className="w-12 h-12 text-primary" />
              )}
            </div>
          </div>

          <h2 className="text-2xl font-display font-bold text-foreground mb-2">
            {built ? "🚀 Site Built!" : "Building your site..."}
          </h2>
          <p className="text-muted-foreground mb-8 text-sm">
            {built ? "Redirecting to your Builder Hub..." : Stage.text}
          </p>

          {/* Progress bar */}
          <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden mb-6">
            <div
              className="h-full bg-gradient-to-r from-primary to-secondary rounded-full transition-all duration-1000"
              style={{ width: `${built ? 100 : ((buildStage + 1) / BUILD_STAGES.length) * 90}%` }}
            />
          </div>

          {/* Stage chips */}
          <div className="flex flex-wrap justify-center gap-2">
            {BUILD_STAGES.map((s, i) => (
              <div
                key={i}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border transition-all duration-500 ${
                  i < buildStage
                    ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-400"
                    : i === buildStage
                    ? "bg-primary/20 border-primary/50 text-primary shadow-[0_0_10px_rgba(0,235,255,0.2)]"
                    : "border-white/10 text-muted-foreground/40"
                }`}
              >
                {i < buildStage ? <Check className="w-3 h-3" /> : <s.icon className="w-3 h-3" />}
                {s.text.replace("...", "")}
              </div>
            ))}
          </div>

          {error && (
            <div className="mt-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ─── Form page ───────────────────────────────────────────────────────────
  return (
    <Layout>
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
          <span className="text-[10px] font-bold text-primary uppercase tracking-widest">New Project</span>
        </div>
        <h1 className="text-3xl font-display font-bold text-foreground">Website Builder</h1>
        <p className="text-muted-foreground mt-1">Configure your project and let DreamAgent build it for you.</p>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-1 mb-8 overflow-x-auto pb-2">
        {STEPS.map((s, i) => (
          <div key={s} className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => i < step && setStep(i)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold transition-all duration-300 ${
                i === step
                  ? "bg-primary text-black shadow-[0_0_12px_rgba(0,235,255,0.4)]"
                  : i < step
                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30 cursor-pointer"
                  : "bg-white/5 text-muted-foreground border border-white/10 cursor-default"
              }`}
            >
              {i < step ? <Check className="w-3 h-3" /> : <span>{i + 1}</span>}
              {s}
            </button>
            {i < STEPS.length - 1 && <div className={`w-4 h-px rounded-full transition-colors ${i < step ? "bg-emerald-500/50" : "bg-white/10"}`} />}
          </div>
        ))}
      </div>

      {/* Form card */}
      <div className="max-w-3xl">
        <div className="glass-panel rounded-3xl p-6 md:p-8 mb-6 animate-fade-in-up">
          {steps[step]}
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-between">
          <button
            onClick={() => setStep(s => Math.max(0, s - 1))}
            disabled={step === 0}
            className="flex items-center gap-2 px-5 py-3 rounded-xl border border-white/10 text-muted-foreground hover:text-foreground hover:border-white/25 hover:bg-white/5 transition-all disabled:opacity-30 disabled:cursor-not-allowed text-sm font-semibold"
          >
            <ChevronLeft className="w-4 h-4" /> Back
          </button>

          {step < STEPS.length - 1 ? (
            <button
              onClick={() => setStep(s => Math.min(STEPS.length - 1, s + 1))}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-primary/10 border border-primary/40 text-primary hover:bg-primary hover:text-black font-bold text-sm transition-all duration-300 shadow-lg shadow-primary/10"
            >
              Next <ChevronRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={handleBuild}
              disabled={building}
              className="flex items-center gap-2 px-8 py-3 rounded-xl bg-gradient-to-r from-primary to-secondary text-black font-bold text-sm transition-all duration-300 shadow-lg shadow-primary/20 hover:shadow-primary/40 hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {building ? <Loader2 className="w-4 h-4 animate-spin" /> : <Rocket className="w-4 h-4" />}
              Build My Website
            </button>
          )}
        </div>
      </div>
    </Layout>
  );
}
