// App shell: logo, sidebar navigation, page header and footer.
import { useEffect, useState } from "react";
import {
  ArrowUpRight, BookOpen, ChartColumn, FolderGit2, Inbox, LayoutDashboard, Mail, MapPin, Menu, MessageCircle, Phone, Scale,
  Settings, ShoppingBag, Users, X,
} from "./icons.jsx";
import { SITE } from "../site.js";
import { cx } from "./ui.jsx";

export const NAV = [
  {
    group: "Shop",
    items: [
      { id: "overview", label: "Overview", icon: LayoutDashboard, desc: "How your shop is doing today" },
      { id: "chat", label: "Customer chat", icon: MessageCircle, desc: "Talk to the assistant exactly as a customer would on WhatsApp" },
      { id: "inbox", label: "Inbox", icon: Inbox, desc: "Alerts that need you, and every customer conversation" },
      { id: "orders", label: "Orders", icon: ShoppingBag, desc: "Orders with a cash-on-delivery risk check, and bookings" },
      { id: "customers", label: "Customers", icon: Users, desc: "Everyone who has ordered, with their history and trust level" },
    ],
  },
  { group: "Grow", items: [{ id: "insights", label: "Insights", icon: ChartColumn, desc: "Sales, AI business advice and market prices" }] },
  { group: "Manage", items: [{ id: "settings", label: "Settings", icon: Settings, desc: "Your menu and prices, AI usage and costs" }] },
];
export const PAGES = NAV.flatMap((g) => g.items);

export function Logo({ size = 36, withText = true, light = false }) {
  return (
    <span className="flex items-center gap-2.5">
      <img src="/logo-mark.png" alt="" width={size} height={size} className="shrink-0" />
      {withText && (
        <span className="leading-tight">
          <span className={cx("block text-[17px] font-extrabold tracking-tight", light ? "text-white" : "text-brand-900")}>
            Dukaan <span className={light ? "text-brand-300" : "text-brand-500"}>Dost</span>
          </span>
          <span className={cx("block text-[11px] font-medium", light ? "text-brand-200" : "text-slate-500")}>{SITE.tagline}</span>
        </span>
      )}
    </span>
  );
}

function NavList({ page, go, alerts, onPick }) {
  return (
    <nav aria-label="Main" className="space-y-6">
      {NAV.map((g) => (
        <div key={g.group}>
          <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">{g.group}</p>
          <ul className="space-y-0.5">
            {g.items.map((it) => {
              const active = page === it.id;
              return (
                <li key={it.id}>
                  <a
                    href={`#/${it.id}`}
                    aria-current={active ? "page" : undefined}
                    onClick={(e) => { e.preventDefault(); go(it.id); onPick?.(); }}
                    className={cx(
                      "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
                      active ? "bg-brand-50 text-brand-800" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                    )}
                  >
                    <it.icon size={18} className={active ? "text-brand-600" : "text-slate-400 group-hover:text-slate-600"} aria-hidden />
                    <span className="flex-1">{it.label}</span>
                    {it.id === "inbox" && alerts > 0 && (
                      <span className="rounded-full bg-red-500 px-1.5 py-0.5 text-[11px] font-semibold leading-none text-white" aria-label={`${alerts} open alerts`}>{alerts}</span>
                    )}
                  </a>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function ShopCard({ shop }) {
  if (!shop) return null;
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <p className="truncate text-sm font-semibold text-slate-800">{shop.name}</p>
      <p className="truncate text-xs text-slate-500">{shop.city || SITE.city}{shop.timings ? ` · ${shop.timings}` : ""}</p>
    </div>
  );
}

export function Sidebar({ page, go, alerts, shop }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    setOpen(false);
  }, [page]); // close the phone menu after moving to another page
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      {/* Laptop: fixed sidebar */}
      <aside className="hidden w-64 shrink-0 border-r border-slate-200 bg-white lg:block">
        <div className="sticky top-0 flex h-screen flex-col px-4 py-5">
          <a href="#/overview" onClick={(e) => { e.preventDefault(); go("overview"); }} className="px-2" aria-label="Dukaan Dost home">
            <Logo />
          </a>
          <div className="mt-8 flex-1 overflow-y-auto scroll-thin">
            <NavList page={page} go={go} alerts={alerts} />
          </div>
          <ShopCard shop={shop} />
        </div>
      </aside>

      {/* Phone / tablet: top bar + slide-in menu */}
      <div className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white/95 px-4 py-2.5 backdrop-blur lg:hidden">
        <Logo size={30} />
        <button onClick={() => setOpen(true)} aria-label="Open menu" aria-expanded={open}
          className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">
          <Menu size={22} />
        </button>
      </div>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col bg-white px-4 py-4 shadow-xl">
            <div className="flex items-center justify-between">
              <Logo size={30} />
              <button onClick={() => setOpen(false)} aria-label="Close menu" className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={20} /></button>
            </div>
            <div className="mt-6 flex-1 overflow-y-auto"><NavList page={page} go={go} alerts={alerts} onPick={() => setOpen(false)} /></div>
            <ShopCard shop={shop} />
          </div>
        </div>
      )}
    </>
  );
}

export function PageHeader({ title, desc, action }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h1>
        {desc && <p className="mt-1 text-sm text-slate-500">{desc}</p>}
      </div>
      {action}
    </div>
  );
}

export function Footer({ go }) {
  const link = "text-sm text-slate-600 transition-colors hover:text-brand-700";
  const pageLink = (id, label) => (
    <li><a href={`#/${id}`} onClick={(e) => { e.preventDefault(); go(id); }} className={link}>{label}</a></li>
  );
  return (
    <footer className="mt-16 border-t border-slate-200 bg-white">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-10 sm:px-6 md:grid-cols-2 lg:grid-cols-[1.6fr_1fr_1fr_1.2fr] lg:px-8">
        <div className="max-w-sm">
          <Logo />
          <p className="mt-4 text-sm leading-relaxed text-slate-600">{SITE.mission}</p>
        </div>
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-900">Product</h3>
          <ul className="mt-3 space-y-2">
            {pageLink("chat", "Customer chat")}
            {pageLink("orders", "Orders and risk check")}
            {pageLink("insights", "Insights and advice")}
            {pageLink("settings", "Shop setup")}
          </ul>
        </div>
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-900">Resources</h3>
          <ul className="mt-3 space-y-2">
            <li><a href={SITE.github} target="_blank" rel="noreferrer" className={cx(link, "inline-flex items-center gap-1.5")}><FolderGit2 size={14} aria-hidden />Source code <ArrowUpRight size={12} aria-hidden /></a></li>
            <li><a href={`${SITE.github}#readme`} target="_blank" rel="noreferrer" className={cx(link, "inline-flex items-center gap-1.5")}><BookOpen size={14} aria-hidden />Setup guide <ArrowUpRight size={12} aria-hidden /></a></li>
            <li><a href={`${SITE.github}/blob/main/LICENSE`} target="_blank" rel="noreferrer" className={cx(link, "inline-flex items-center gap-1.5")}><Scale size={14} aria-hidden />MIT License <ArrowUpRight size={12} aria-hidden /></a></li>
          </ul>
        </div>
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-900">Contact</h3>
          <ul className="mt-3 space-y-2">
            {SITE.email && <li><a href={`mailto:${SITE.email}`} className={cx(link, "inline-flex items-center gap-2 break-all")}><Mail size={14} className="shrink-0" aria-hidden />{SITE.email}</a></li>}
            {SITE.phone && <li><a href={`tel:${SITE.phone.replace(/\s/g, "")}`} className={cx(link, "inline-flex items-center gap-2")}><Phone size={14} aria-hidden />{SITE.phone}</a></li>}
            <li className="inline-flex items-center gap-2 text-sm text-slate-600"><MapPin size={14} aria-hidden />{SITE.city}</li>
          </ul>
        </div>
      </div>
      <div className="border-t border-slate-100">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-5 text-xs text-slate-500 sm:px-6 md:flex-row md:items-center md:justify-between lg:px-8">
          <p>© {SITE.year} {SITE.name}. Built for the Nebius × NVIDIA Global AI Hackathon.</p>
          <p>Powered by NVIDIA Nemotron on Nebius Token Factory</p>
        </div>
      </div>
    </footer>
  );
}
