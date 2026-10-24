// Daily / monthly numbers (calculated in Python) + AI business advice from Nemotron 3 Ultra.
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, niceStamp, rs, thisMonth, todayISO, useApi } from "../api.js";
import { Badge, Button, Card, Empty, ErrorBox, Loading, Stat } from "../components/ui.jsx";

function Change({ v, label }) {
  if (v === null || v === undefined) return null;
  return <span className={v >= 0 ? "text-green-700" : "text-red-700"}>{v > 0 ? "+" : ""}{v}% {label}</span>;
}

function Advice({ month }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function get(refresh = false) {
    setBusy(true);
    setError(null);
    try {
      setData(await api("/advice/monthly", { params: { month, language: "english", refresh: refresh || undefined } }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title="🧠 AI business advisor"
      action={
        data ? (
          <Button kind="ghost" onClick={() => get(true)} disabled={busy}>Ask again</Button>
        ) : (
          <Button onClick={() => get(false)} disabled={busy}>{busy ? "Thinking…" : "Get advice"}</Button>
        )
      }
    >
      <p className="text-xs text-slate-500">
        <b>Nemotron 3 Ultra</b> reads this month's numbers (all calculated in code) and suggests what to do next.
        It runs only when you ask, and the answer is saved, so opening it again is free.
      </p>
      <ErrorBox error={error} />
      {busy && <Loading text="Nemotron Ultra is thinking… this can take up to a minute." />}
      {data && !busy && (
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            {data.model_used && <Badge color={String(data.model_used).toLowerCase().includes("ultra") ? "green" : "slate"}>{data.model_used}</Badge>}
            {data.cached && <Badge color="blue">saved answer</Badge>}
            {data.generated_at && <span className="text-xs text-slate-400">{niceStamp(data.generated_at)}</span>}
          </div>
          {data.note && <div className="text-xs text-amber-700">{data.note}</div>}
          {data.headline && <p className="font-medium text-slate-800">{data.headline}</p>}
          {!data.tips?.length ? <Empty>No advice yet: there are no orders this month.</Empty> : (
            <ol className="space-y-2">
              {data.tips.map((t, i) => (
                <li key={i} className="rounded-xl bg-green-50 p-3">
                  <div className="font-semibold text-green-900">{i + 1}. {t.title}</div>
                  <div className="mt-0.5 text-sm text-slate-700">{t.detail}</div>
                  {t.based_on && <div className="mt-1 text-xs text-slate-500">Based on: {t.based_on}</div>}
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </Card>
  );
}

export default function Summary() {
  const [tab, setTab] = useState("month");
  const [day, setDay] = useState(todayISO());
  const [month, setMonth] = useState(thisMonth());
  const daily = useApi("/summary/daily", { params: { date: day, language: "english" }, skip: tab !== "day", ms: 60000 });
  const monthly = useApi("/summary/monthly", { params: { month, language: "english" }, skip: tab !== "month", ms: 60000 });
  const s = tab === "day" ? daily : monthly;
  const d = s.data;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-xl border border-slate-200 bg-white p-1">
          {[["day", "Day"], ["month", "Month"]].map(([id, label]) => (
            <button key={id} onClick={() => setTab(id)} className={`rounded-lg px-4 py-1.5 text-sm ${tab === id ? "bg-green-600 text-white" : "text-slate-600"}`}>{label}</button>
          ))}
        </div>
        {tab === "day" ? (
          <input type="date" value={day} onChange={(e) => setDay(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" />
        ) : (
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" />
        )}
      </div>

      <ErrorBox error={s.error} />
      {s.loading && !d ? <Loading /> : d && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Orders" value={d.orders} sub={d.cancelled ? `${d.cancelled} cancelled` : "no cancellations"} />
            <Stat label="Sales" value={rs(d.sales)} sub={<Change v={tab === "day" ? d.sales_change_percent_vs_yesterday : d.sales_change_percent_vs_last_month} label={tab === "day" ? "vs yesterday" : "vs last month"} />} />
            <Stat label="Profit" value={rs(d.profit)} tone="green" />
            <Stat label="Average order" value={rs(d.average_order)} sub={d.high_risk_orders ? `${d.high_risk_orders} high-risk COD` : null} />
          </div>

          {d.note && (
            <Card title="AI note (Nemotron Nano)"><p className="text-sm text-slate-700">{d.note}</p></Card>
          )}

          {tab === "month" && (
            <Card title="Daily sales and profit">
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={(d.daily_chart || []).map((x) => ({ ...x, day: Number(x.date.slice(8)) }))}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="day" tickLine={false} fontSize={12} />
                    <YAxis tickFormatter={(v) => (v >= 1000 ? `${Math.round(v / 1000)}k` : v)} fontSize={12} width={40} />
                    <Tooltip formatter={(v) => rs(v)} labelFormatter={(l) => `Day ${l}`} />
                    <Legend />
                    <Bar dataKey="sales" name="Sales (Rs)" fill="#16a34a" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="profit" name="Profit (Rs)" fill="#86efac" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          )}

          <Card title="Top products">
            {!d.top_products?.length ? <Empty>No sales in this period.</Empty> : (
              <ul className="space-y-2">
                {d.top_products.map((p, i) => (
                  <li key={p.name} className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2 text-sm">
                    <span>{["🥇", "🥈", "🥉"][i] || "•"} {p.name}</span>
                    <span className="font-semibold">{p.quantity} sold</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}

      {tab === "month" && <Advice key={month} month={month} />}
      {tab === "day" && <NightlyReport />}
    </div>
  );
}

// The nightly owner report (runs by itself as a background job; this button runs it now).
function NightlyReport() {
  const reports = useApi("/reports", { ms: 0 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  async function makeNow() {
    setBusy(true);
    setError(null);
    try {
      await api("/admin/run-daily-report", { method: "POST" });
      reports.reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const last = reports.data?.[0];
  return (
    <Card title="Nightly owner report" action={<Button kind="ghost" onClick={makeNow} disabled={busy}>{busy ? "Making…" : "Make today's report now"}</Button>}>
      <p className="mb-2 text-sm text-slate-600">
        Every night a background job (a Nebius Serverless Job) adds up the day and sends this report to the
        owner's WhatsApp.
      </p>
      <ErrorBox error={error} />
      {last ? (
        <pre className="whitespace-pre-wrap rounded-xl bg-slate-50 p-3 font-sans text-sm text-slate-800">{last.text}</pre>
      ) : (
        <Empty>No report yet.</Empty>
      )}
    </Card>
  );
}
