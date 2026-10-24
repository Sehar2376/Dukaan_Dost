// How much AI was used today (estimated from real token counts) + demo tools.
import { useState } from "react";
import { api, useApi } from "../api.js";
import { Button, Card, ErrorBox, Loading, Stat, Table } from "../components/ui.jsx";

const usd = (n) => "$" + (Number(n) || 0).toFixed(4);

export default function Usage() {
  const { data, error, loading, reload } = useApi("/usage");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  async function loadDemo() {
    if (!window.confirm("This replaces all orders, customers, chats and alerts with demo data. Continue?")) return;
    setBusy(true);
    setMsg(null);
    try {
      const r = await api("/admin/load-demo", { method: "POST" });
      setMsg(`Loaded ${r.orders} demo orders and ${r.customers} customers (${r.database}).`);
      reload();
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <ErrorBox error={error} />
      {loading && !data ? <Loading /> : data && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Messages today" value={data.messages} sub={`limit ${data.limits.total_per_day}/day`} />
            <Stat label="AI calls today" value={data.ai_calls} />
            <Stat label="Tokens today" value={(data.prompt_tokens + data.completion_tokens).toLocaleString()} />
            <Stat label="Estimated cost" value={usd(data.estimated_cost_usd)} sub={`budget $${data.limits.daily_budget_usd}/day`}
              tone={data.estimated_cost_usd >= data.limits.daily_budget_usd ? "red" : "green"} />
          </div>
          <Card title="Today by model">
            <Table head={["What", "Calls", "Estimated cost"]}>
              {[["Nemotron Nano (every message)", "nano"], ["Nemotron Super (orders, setup, market)", "super"], ["Nemotron Ultra (advice)", "ultra"]].map(([label, k]) => (
                <tr key={k}><td className="px-3 py-2">{label}</td><td className="px-3 py-2">{data.by_model?.[k]?.calls ?? 0}</td><td className="px-3 py-2">{usd(data.by_model?.[k]?.cost_usd)}</td></tr>
              ))}
              <tr><td className="px-3 py-2">Tavily web searches</td><td className="px-3 py-2">{data.tavily_searches ?? 0} / {data.limits.tavily_per_day}</td><td className="px-3 py-2 text-slate-500">free plan credits</td></tr>
            </Table>
          </Card>
          <Card title="Credit protection">
            <ul className="space-y-1 text-sm text-slate-700">
              <li>• Max <b>{data.limits.per_phone_per_day}</b> messages per phone number per day</li>
              <li>• Max <b>{data.limits.total_per_day}</b> messages for the whole app per day</li>
              <li>• AI pauses automatically after <b>${data.limits.daily_budget_usd}</b> estimated spend per day</li>
              <li>• Nano for every message, Super for orders, Ultra only when you ask for advice</li>
              <li>• Max <b>{data.limits.tavily_per_day}</b> Tavily market searches per day; each result is saved for 24 hours</li>
            </ul>
          </Card>
          <Card title="Last days">
            <Table head={["Date", "Messages", "Estimated cost"]}>
              {data.history.map((h) => (
                <tr key={h.date}><td className="px-3 py-2">{h.date}</td><td className="px-3 py-2">{h.messages}</td><td className="px-3 py-2">{usd(h.estimated_cost_usd)}</td></tr>
              ))}
            </Table>
          </Card>
        </>
      )}
      <Card title="Demo tools">
        <p className="mb-2 text-sm text-slate-600">Fill the app with labelled demo data: a bakery, 20 customers and about 3 months of orders.</p>
        <Button kind="dark" onClick={loadDemo} disabled={busy}>{busy ? "Loading…" : "Load demo data"}</Button>
        {msg && <div className="mt-2 text-sm text-slate-600">{msg}</div>}
      </Card>
    </div>
  );
}
