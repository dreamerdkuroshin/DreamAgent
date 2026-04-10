import React from "react";
import { cn } from "@/lib/utils";

// --- Button ---
export const Button = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "outline" | "ghost" | "destructive", size?: "sm" | "md" | "lg" }>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => {
    const base = "inline-flex items-center justify-center rounded-xl font-semibold transition-all duration-300 disabled:opacity-50 disabled:pointer-events-none active:scale-95";
    const variants = {
      primary: "bg-primary text-black hover:bg-primary/90 shadow-[0_0_15px_rgba(0,240,255,0.3)] hover:shadow-[0_0_25px_rgba(0,240,255,0.5)]",
      secondary: "bg-secondary text-white hover:bg-secondary/90 shadow-[0_0_15px_rgba(139,92,246,0.3)]",
      outline: "border-2 border-primary/50 text-primary hover:bg-primary/10",
      ghost: "text-muted-foreground hover:text-foreground hover:bg-white/5",
      destructive: "bg-destructive text-white hover:bg-destructive/90 shadow-[0_0_15px_rgba(220,38,38,0.4)]",
    };
    const sizes = { sm: "px-3 py-1.5 text-xs", md: "px-4 py-2 text-sm", lg: "px-6 py-3 text-base" };
    
    return (
      <button ref={ref} className={cn(base, variants[variant], sizes[size], className)} {...props} />
    );
  }
);
Button.displayName = "Button";

// --- Card ---
export const Card = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("glass-panel rounded-2xl overflow-hidden relative group", className)} {...props}>
    {/* Hover highlight effect */}
    <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none" />
    {children}
  </div>
);

// --- Input ---
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "flex h-11 w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-foreground",
        "placeholder:text-muted-foreground transition-all duration-300",
        "focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary shadow-inner",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";

// --- Badge ---
export const Badge = ({ className, variant = "default", children }: React.HTMLAttributes<HTMLSpanElement> & { variant?: "success" | "warning" | "error" | "default" | "neon" }) => {
  const variants = {
    default: "bg-white/10 text-foreground border-white/5",
    success: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    warning: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    error: "bg-red-500/10 text-red-400 border-red-500/20",
    neon: "bg-primary/10 text-primary border-primary/30 shadow-[0_0_10px_rgba(0,240,255,0.3)]",
  };
  return (
    <span className={cn("inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border backdrop-blur-sm", variants[variant], className)}>
      {children}
    </span>
  );
};

// --- Modal ---
export const Modal = ({ isOpen, onClose, title, children }: { isOpen: boolean, onClose: () => void, title: string, children: React.ReactNode }) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm">
      <div className="absolute inset-0" onClick={onClose} />
      <div className="relative w-full max-w-lg glass-panel rounded-2xl p-6 shadow-[0_0_50px_rgba(0,0,0,0.5)] border border-white/10 animate-in fade-in zoom-in-95 duration-200">
        <h2 className="text-xl font-display font-bold text-foreground mb-4">{title}</h2>
        {children}
      </div>
    </div>
  );
};
