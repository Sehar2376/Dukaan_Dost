// Overview: getting-started steps, today's numbers, what needs attention, recent orders, how it works.
import { useState } from "react";
import {
  ArrowRight, Bell, Bot, Check, Cpu, Database, MessageCircle, Search, ShieldCheck, ShoppingBag, Sparkles, TrendingUp, Wallet, X,
} from "../components/icons.jsx";
import { api, clean, niceStamp, rs, useApi } from "../api.js";
import {
  Button, Card, EmptyState, ErrorNotice, FlagBadge, LoadingRows, ModelChip, RiskBadge, Stat, cx, store, useToast,
} from "../components/ui.jsx";

function GettingStarted({ hasOrders, go, onLoaded }) {
  const toast = useToast();
  const [hidden, setHidden] = useState(() => store.get("dd_onboarding_hidden", false));
  const [busy, setBusy] = useState(false);
  if (hidden) return null;
  const chatted = store.get("dd_chatted", false);
  const seenOrders = store.get("dd_seen_orders", false);

  async function load() {
    setBusy(true);
    try {
      const r = await api("/admin/load-demo", { method: "POST" });
      toast(`Sample shop loaded: ${r.orders} orders and ${r.customers} customers.`);
      onLoaded();
    } catch (e) {
      toast(e.message, "danger");
    } finally {
      setBusy(false);
    }
  }

  const steps = [
    { done: hasOrders, title: "Load the sample shop", text: "A Karachi home bakery with 20 customers and three months of orders.",
      action: <Button size="sm" onClick={load} loading={busy} disabled={hasOrders}>{hasOrders ? "Loaded" : "Load sample shop"}</Button> },
    { done: chatted, title: "Order as a customer", text: "Ask for a cake in Roman Urdu, try to bargain, then confirm the order.",
      action: <Button size="sm" variant="secondary" icon={MessageCircle} onClick={() => go("chat")}>Open customer chat</Button> },
    { done: seenOrders, title: "Review it as the owner", text: "See the new order, its cash-on-delivery risk check and any alerts.",
      action: <Button size="sm" variant="secondary" icon={ShoppingBag} onClick={() => go("orders")}>View orders</Button> },
  ];
  const doneCount = steps.filter((s) => s.done).length;

  return (
    <Card
      title="Get started in two minutes"
      subtitle={`${doneCount} of 3 steps done`}
      icon={Sparkles}
      action={
        <button onClick={() => { store.set("dd_onboarding_hidden", true); setHidden(true); }} aria-label="Hide getting started"
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"><X size={16} /></button>
      }
    >
      <ol className="grid gap-3 md:grid-cols-3">
        {steps.map((s, i) => (
          <li key={s.title} className={cx("flex flex-col rounded-xl border p-4", s.done ? "border-emerald-200 bg-emerald-50/50" : "border-slate-200")}>
            <div className="flex items-center gap-2.5">
              <span className={cx("flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold",
                s.done ? "bg-emerald-600 text-white" : "bg-brand-100 text-brand-700")}>
                {s.done ? <Check size={14} aria-label="Done" /> : i + 1}
              </span>
              <span className="text-sm font-semibold text-slate-900">{s.title}</span>
            </div>
            <p className="mt-2 flex-1 text-sm text-slate-600">{s.text}</p>
            <div className="mt-3">{s.action}</div>
          </li>
        ))}
      </ol>
    </Card>
  );
}

function HowItWorks() {
  const steps = [
    { icon: MessageCircle, title: "Customer writes", text: "On WhatsApp, in Urdu, Roman Urdu or English." },
    { icon: Cpu, title: "Reads every message", model: "nano", text: "Detects language and intent, answers simple questions instantly." },
    { icon: Bot, title: "Handles the sale", model: "super", text: "An agent that quotes prices, bargains within your limits and books orders using 7 tools." },
    { icon: ShieldCheck, title: "Protects the owner", text: "Prices, discounts and COD risk are checked in code. Risky orders and complaints reach you." },
  ];
  return (
    <Card title="How Dukaan Dost works" subtitle="Each job goes to the smallest model that can do it well, so replies stay fast and cheap." icon={Sparkles}>
      <ol className="grid gap-3 md:grid-cols-4">
        {steps.map((s, i) => (
          <li key={s.title} className="relative rounded-xl border border-slate-200 p-4">
            <div className="flex items-center justify-between">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><s.icon size={18} aria-hidden /></span>
              {s.model && <ModelChip model={s.model} />}
            </div>
            <p className="mt-3 text-sm font-semibold text-slate-900">{s.title}</p>
            <p className="mt-1 text-sm text-slate-600">{s.text}</p>
            {i < steps.length - 1 && (
              <ArrowRight size={16} aria-hidden className="absolute -right-[13px] top-1/2 z-10 hidden -translate-y-1/2 rounded-full bg-white text-slate-300 md:block" />
            )}
          </li>
        ))}
      </ol>
      <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-slate-100 pt-4 text-sm text-slate-600">
        <span className="inline-flex items-center gap-2"><ModelChip model="ultra" /> Monthly business advice, only when you ask</span>
        <span className="inline-flex items-center gap-2"><Search size={15} className="text-slate-400" aria-hidden /> Tavily web search for competitor prices</span>
        <span className="inline-flex items-center gap-2"><Database size={15} className="text-slate-400" aria-hidden /> Runs on Nebius Token Factory</span>
      </div>
    </Card>
  );
}

export default function Overview({ go, refreshFlags }) {
  const today = useApi("/summary/daily");
  const flags = useApi("/flags");
  const orders = useApi("/orders");
  const t = today.data;
  const recent = (orders.data || []).slice(0, 6);
  const urgent = (flags.data || []).slice(0, 5);
  const reloadAll = () => { today.reload(); flags.reload(); orders.reload(); refreshFlags?.(); };

  return (
    <div className="space-y-6">
      <GettingStarted hasOrders={(orders.data || []).length > 0} go={go} onLoaded={reloadAll} />
      <ErrorNotice error={today.error} />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Orders today" icon={ShoppingBag} value={t ? t.orders : "—"} hint={t ? (t.cancelled ? `${t.cancelled} cancelled` : "No cancellations") : null} />
        <Stat label="Sales today" icon={TrendingUp} value={t ? rs(t.sales) : "—"} delta={t?.sales_change_percent_vs_yesterday} deltaLabel="vs yesterday" />
        <Stat label="Profit today" icon={Wallet} value={t ? rs(t.profit) : "—"} tone="success" />
        <Stat label="Open alerts" icon={Bell} value={flags.data ? flags.data.length : "—"} tone={flags.data?.length ? "danger" : "neutral"} hint="Need your reply" />
      </div>

      {t?.note && (
        <div className="flex gap-3 rounded-2xl border border-brand-100 bg-brand-50/60 p-4">
          <Sparkles size={18} className="mt-0.5 shrink-0 text-brand-600" aria-hidden />
          <div className="text-sm">
            <p className="font-semibold text-brand-900">Today in brief</p>
            <p className="mt-0.5 text-slate-700">{clean(t.note)}</p>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Needs your attention" icon={Bell} action={<Button size="sm" variant="ghost" onClick={() => go("inbox")}>View all</Button>}>
          {flags.loading && !flags.data ? <LoadingRows /> : urgent.length === 0 ? (
            <EmptyState icon={Check} title="You're all caught up">No complaints, risky orders or unanswered questions right now.</EmptyState>
          ) : (
            <ul className="-my-2 divide-y divide-slate-100">
              {urgent.map((f) => (
                <li key={f.id} className="flex items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2"><FlagBadge type={f.type} /><span className="text-xs text-slate-500">{f.phone_masked} · {niceStamp(f.created_at)}</span></div>
                    <p className="mt-1 truncate text-sm text-slate-700">{f.reason}</p>
                  </div>
                  <Button size="sm" variant="secondary" onClick={() => go("inbox", { phone: f.customer_phone })}>Open</Button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Recent orders" icon={ShoppingBag} action={<Button size="sm" variant="ghost" onClick={() => go("orders")}>View all</Button>}>
          {orders.loading && !orders.data ? <LoadingRows /> : recent.length === 0 ? (
            <EmptyState icon={ShoppingBag} title="No orders yet">Load the sample shop above, or place an order from the customer chat.</EmptyState>
          ) : (
            <ul className="-my-2 divide-y divide-slate-100">
              {recent.map((o) => (
                <li key={o.id} className="flex items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-900">{o.customer_name || o.phone_masked}</p>
                    <p className="truncate text-xs text-slate-500">{niceStamp(o.created_at)} · {o.items.map((i) => `${i.quantity}× ${i.name}`).join(", ")}</p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <span className="text-sm font-semibold text-slate-900">{rs(o.total)}</span>
                    <RiskBadge level={o.risk_level} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <HowItWorks />
    </div>
  );
}
