import { useState } from "react";
import { api, niceStamp, rs, useApi } from "../api.js";
import { Button, Card, Empty, ErrorBox, FlagBadge, Loading, RiskBadge, Stat } from "../components/ui.jsx";

export default function Home({ go }) {
  const today = useApi("/summary/daily");
  const flags = useApi("/flags");
  const orders = useApi("/orders");
  const [loadingDemo, setLoadingDemo] = useState(false);
  const [msg, setMsg] = useState(null);

  async function loadDemo() {
    setLoadingDemo(true);
    setMsg(null);
    try {
      const r = await api("/admin/load-demo", { method: "POST" });
      setMsg(`Loaded ${r.orders} demo orders and ${r.customers} customers.`);
      today.reload();
      flags.reload();
      orders.reload();
    } catch (e) {
      setMsg(e.message);
    } finally {
      setLoadingDemo(false);
    }
  }

  const t = today.data;
  const recent = (orders.data || []).slice(0, 6);
  const urgent = (flags.data || []).slice(0, 5);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Assalam o alaikum 👋</h1>
        <p className="text-sm text-slate-500">Here's your shop today. Updates every 30 seconds.</p>
      </div>
      <ErrorBox error={today.error} />

      {orders.data && orders.data.length === 0 && (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm text-slate-600">No orders yet. Load demo data to see the dashboard in action.</div>
            <Button onClick={loadDemo} disabled={loadingDemo}>{loadingDemo ? "Loading…" : "Load demo data"}</Button>
          </div>
          {msg && <div className="mt-2 text-sm text-slate-600">{msg}</div>}
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Orders today" value={t ? t.orders : "…"} sub={t && t.cancelled ? `${t.cancelled} cancelled` : null} />
        <Stat label="Sales today" value={t ? rs(t.sales) : "…"}
          sub={t && t.sales_change_percent_vs_yesterday != null ? `${t.sales_change_percent_vs_yesterday > 0 ? "+" : ""}${t.sales_change_percent_vs_yesterday}% vs yesterday` : null} />
        <Stat label="Profit today" value={t ? rs(t.profit) : "…"} tone="green" />
        <Stat label="Open alerts" value={flags.data ? flags.data.length : "…"} tone={flags.data?.length ? "red" : "slate"} />
      </div>

      {t?.note && (
        <Card title="Today in a few words">
          <p className="text-sm text-slate-700">{t.note}</p>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="🚨 Needs your attention" action={<Button kind="ghost" onClick={() => go("alerts")}>All alerts</Button>}>
          {flags.loading && !flags.data ? <Loading /> : urgent.length === 0 ? <Empty>Nothing urgent. 🎉</Empty> : (
            <ul className="space-y-2">
              {urgent.map((f) => (
                <li key={f.id} className="flex items-start justify-between gap-3 rounded-xl bg-slate-50 p-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2"><FlagBadge type={f.type} /><span className="text-xs text-slate-500">{f.phone_masked}</span></div>
                    <div className="mt-1 truncate text-sm text-slate-700">{f.reason}</div>
                  </div>
                  <Button kind="ghost" onClick={() => go("chats", f.customer_phone)}>Open chat</Button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="🧾 Recent orders" action={<Button kind="ghost" onClick={() => go("orders")}>All orders</Button>}>
          {orders.loading && !orders.data ? <Loading /> : recent.length === 0 ? <Empty>No orders yet.</Empty> : (
            <ul className="divide-y divide-slate-100">
              {recent.map((o) => (
                <li key={o.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <div className="min-w-0">
                    <div className="font-medium text-slate-800">{o.customer_name || o.phone_masked}</div>
                    <div className="truncate text-xs text-slate-500">{niceStamp(o.created_at)} · {o.items.map((i) => `${i.quantity}× ${i.name}`).join(", ")}</div>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <span className="font-semibold">{rs(o.total)}</span>
                    <RiskBadge level={o.risk_level} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
