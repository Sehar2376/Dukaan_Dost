// Shared building blocks: cards, buttons, badges, tabs, tables, empty and loading states, toasts.
import { createContext, useCallback, useContext, useState } from "react";
import {
  Ban, CircleAlert, CircleCheck, Flame, HelpCircle, Info, LoaderCircle, MessageSquareWarning, PackageOpen, ShieldAlert,
  TriangleAlert, X,
} from "./icons.jsx";

export const cx = (...a) => a.filter(Boolean).join(" ");

export const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 " +
  "focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 disabled:bg-slate-50 disabled:text-slate-500";

// ---------------------------------------------------------------- layout pieces
export function Card({ title, subtitle, icon: Icon, action, children, className = "", bodyClass = "p-5", id }) {
  return (
    <section id={id} className={cx("min-w-0 rounded-2xl border border-slate-200/80 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)]", className)}>
      {(title || action) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
          <div className="flex min-w-0 items-start gap-3">
            {Icon && (
              <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                <Icon size={16} aria-hidden />
              </span>
            )}
            <div className="min-w-0">
              {title && <h2 className="text-[15px] font-semibold text-slate-900">{title}</h2>}
              {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
            </div>
          </div>
          {action && <div className="flex shrink-0 flex-wrap items-center gap-2">{action}</div>}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  );
}

const BTN = {
  primary: "bg-brand-600 text-white hover:bg-brand-700 shadow-sm",
  secondary: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 shadow-sm",
  subtle: "bg-brand-50 text-brand-700 hover:bg-brand-100",
  ghost: "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
  danger: "bg-red-600 text-white hover:bg-red-700 shadow-sm",
};
const SIZE = { sm: "h-8 px-3 text-[13px]", md: "h-9 px-3.5 text-sm", lg: "h-11 px-5 text-[15px]", icon: "h-9 w-9" };

export function Button({ variant = "primary", size = "md", icon: Icon, loading = false, className = "", children, ...props }) {
  return (
    <button
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
        BTN[variant], SIZE[size], className
      )}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? <LoaderCircle size={16} className="animate-spin" aria-hidden /> : Icon ? <Icon size={16} aria-hidden /> : null}
      {children}
    </button>
  );
}

// ---------------------------------------------------------------- badges
const TONE = {
  neutral: "bg-slate-100 text-slate-700 ring-slate-200",
  brand: "bg-brand-50 text-brand-700 ring-brand-200",
  success: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  warning: "bg-amber-50 text-amber-800 ring-amber-200",
  danger: "bg-red-50 text-red-700 ring-red-200",
  violet: "bg-violet-50 text-violet-700 ring-violet-200",
};
const DOT = { neutral: "bg-slate-400", brand: "bg-brand-500", success: "bg-emerald-500", warning: "bg-amber-500", danger: "bg-red-500", violet: "bg-violet-500" };

export function Badge({ tone = "neutral", icon: Icon, dot = false, title, children, className = "" }) {
  return (
    <span title={title} className={cx("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset", TONE[tone], className)}>
      {dot && <span className={cx("h-1.5 w-1.5 rounded-full", DOT[tone])} aria-hidden />}
      {Icon && <Icon size={12} aria-hidden />}
      {children}
    </span>
  );
}

export function RiskBadge({ level }) {
  const t = { low: ["success", "Low risk"], medium: ["warning", "Medium risk"], high: ["danger", "High risk"] }[level];
  return t ? <Badge tone={t[0]} dot>{t[1]}</Badge> : <span className="text-slate-400">—</span>;
}

export const FLAG = {
  high_risk: { tone: "danger", label: "High-risk COD", icon: ShieldAlert },
  large_order: { tone: "violet", label: "Large order", icon: PackageOpen },
  complaint: { tone: "warning", label: "Complaint", icon: MessageSquareWarning },
  urgent: { tone: "danger", label: "Urgent", icon: Flame },
  question: { tone: "brand", label: "Question", icon: HelpCircle },
  abuse: { tone: "neutral", label: "Abusive message", icon: Ban },
};
export function FlagBadge({ type }) {
  const f = FLAG[type] || { tone: "neutral", label: type };
  return <Badge tone={f.tone} icon={f.icon}>{f.label}</Badge>;
}

const STATUS = { new: "brand", confirmed: "violet", delivered: "success", cancelled: "neutral" };
export function StatusBadge({ status }) {
  return <Badge tone={STATUS[status] || "neutral"} dot className="capitalize">{status}</Badge>;
}

// ---------------------------------------------------------------- numbers
export function Stat({ label, value, icon: Icon, delta, deltaLabel, hint, tone = "neutral" }) {
  const valueTone = { neutral: "text-slate-900", success: "text-emerald-700", danger: "text-red-600" }[tone];
  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium text-slate-500">{label}</span>
        {Icon && <Icon size={16} className="text-slate-400" aria-hidden />}
      </div>
      <div className={cx("mt-2 text-2xl font-bold tracking-tight", valueTone)}>{value}</div>
      {delta !== undefined && delta !== null ? (
        <div className={cx("mt-1 text-xs font-medium", delta >= 0 ? "text-emerald-700" : "text-red-600")}>
          {delta > 0 ? "+" : ""}{delta}% <span className="font-normal text-slate-500">{deltaLabel}</span>
        </div>
      ) : hint ? (
        <div className="mt-1 text-xs text-slate-500">{hint}</div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------- tabs
export function Tabs({ tabs, value, onChange, className = "" }) {
  return (
    <div role="tablist" className={cx("flex gap-1 overflow-x-auto border-b border-slate-200", className)}>
      {tabs.map((t) => {
        const active = t.id === value;
        return (
          <button
            key={t.id}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(t.id)}
            className={cx(
              "-mb-px inline-flex shrink-0 items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
              active ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-800"
            )}
          >
            {t.icon && <t.icon size={15} aria-hidden />}
            {t.label}
            {t.count ? (
              <span className={cx("rounded-full px-1.5 text-[11px] font-semibold", active ? "bg-brand-100 text-brand-700" : "bg-slate-100 text-slate-600")}>{t.count}</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

export function Segmented({ options, value, onChange, label }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5">
      {options.map(([id, text]) => (
        <button
          key={id}
          role="radio"
          aria-checked={value === id}
          onClick={() => onChange(id)}
          className={cx(
            "rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
            value === id ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"
          )}
        >
          {text}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- states
export function EmptyState({ icon: Icon = Info, title, children, action }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 px-6 py-10 text-center">
      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-500"><Icon size={18} aria-hidden /></span>
      {title && <p className="mt-3 text-sm font-semibold text-slate-800">{title}</p>}
      {children && <p className="mt-1 max-w-sm text-sm text-slate-500">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Skeleton({ className = "" }) {
  return <div className={cx("animate-pulse rounded-md bg-slate-200/70", className)} />;
}

export function LoadingRows({ rows = 3 }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
    </div>
  );
}

const NOTICE = {
  danger: ["border-red-200 bg-red-50 text-red-800", CircleAlert],
  warning: ["border-amber-200 bg-amber-50 text-amber-900", TriangleAlert],
  info: ["border-brand-200 bg-brand-50 text-brand-900", Info],
  success: ["border-emerald-200 bg-emerald-50 text-emerald-800", CircleCheck],
};
export function Notice({ tone = "info", title, children, className = "" }) {
  const [cls, Icon] = NOTICE[tone];
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cx("flex gap-3 rounded-xl border p-3.5 text-sm", cls, className)}>
      <Icon size={18} className="mt-0.5 shrink-0" aria-hidden />
      <div className="min-w-0">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={title ? "mt-0.5 opacity-90" : ""}>{children}</div>}
      </div>
    </div>
  );
}

export function ErrorNotice({ error, className = "" }) {
  return error ? <Notice tone="danger" className={className}>{error}</Notice> : null;
}

// ---------------------------------------------------------------- table
export function Table({ head, children, minWidth = 640 }) {
  return (
    <div className="-mx-5 overflow-x-auto scroll-thin">
      <table className="w-full text-left text-sm" style={{ minWidth }}>
        <thead>
          <tr className="border-y border-slate-100 bg-slate-50/70 text-xs font-semibold uppercase tracking-wide text-slate-500">
            {head.map((h, i) => <th key={i} scope="col" className="px-5 py-2.5 font-semibold">{h}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">{children}</tbody>
      </table>
    </div>
  );
}
export const td = "px-5 py-3 align-top";

// ---------------------------------------------------------------- toasts
const ToastCtx = createContext(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const push = useCallback((text, tone = "success") => {
    const id = Math.random().toString(36).slice(2);
    setItems((x) => [...x, { id, text, tone }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 4000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[min(92vw,360px)] flex-col gap-2">
        {items.map((t) => {
          const [cls, Icon] = NOTICE[t.tone] || NOTICE.info;
          return (
            <div key={t.id} className={cx("pointer-events-auto flex items-start gap-2.5 rounded-xl border bg-white p-3 text-sm shadow-lg", cls)}>
              <Icon size={17} className="mt-0.5 shrink-0" aria-hidden />
              <span className="flex-1">{t.text}</span>
              <button onClick={() => setItems((x) => x.filter((y) => y.id !== t.id))} aria-label="Dismiss" className="opacity-60 hover:opacity-100">
                <X size={15} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastCtx.Provider>
  );
}

// ---------------------------------------------------------------- small helpers
export function Field({ label, hint, children }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-slate-700">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </label>
  );
}

export function ModelChip({ model }) {
  const m = {
    nano: ["Nemotron Nano", "bg-sky-50 text-sky-700 ring-sky-200"],
    super: ["Nemotron Super", "bg-brand-50 text-brand-700 ring-brand-200"],
    ultra: ["Nemotron Ultra", "bg-violet-50 text-violet-700 ring-violet-200"],
    practice: ["Practice rules", "bg-slate-100 text-slate-600 ring-slate-200"],
  }[model] || [model, "bg-slate-100 text-slate-600 ring-slate-200"];
  return <span className={cx("inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-semibold ring-1 ring-inset", m[1])}>{m[0]}</span>;
}

// Safe localStorage (private windows can throw)
export const store = {
  get(k, d = null) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ } },
};
