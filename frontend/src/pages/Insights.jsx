// Insights: sales numbers (calculated in code), Nemotron Ultra business advice, and Tavily market prices.
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Brain, ChartColumn, ExternalLink, FileText, Lightbulb, Package, RefreshCw, Search, ShoppingBag, Sparkles, TrendingUp, Wallet } from "../components/icons.jsx";
import { api, clean, niceStamp, rs, thisMonth, todayISO, useApi } from "../api.js";
import {
  Badge, Button, Card, EmptyState, ErrorNotice, LoadingRows, ModelChip, Notice, Segmented, Skeleton, Stat, Tabs, cx, inputCls, useToast,
} from "../components/ui.jsx";

// ---------------------------------------------------------------- Sales
function NightlyReport() {
  const toast = useToast();
  const reports = useApi("/reports", { ms: 0 });
  const [busy, setBusy] = useState(false);
  async function makeNow() {
    setBusy(true);
    try {
      await api("/admin/run-daily-report", { method: "POST" });
      await reports.reload();
      toast("Today's report is ready.");
    } catch (e) {
      toast(e.message, "danger");
    } finally {
      setBusy(false);
    }
  }
  const last = reports.data?.[0];
  return (
    <Card title="End-of-day report" subtitle="Sent to the owner's WhatsApp every night by a background job" icon={FileText}
      action={<Button size="sm" variant="secondary" icon={RefreshCw} onClick={makeNow} loading={busy}>Create now</Button>}>
      {reports.loading && !reports.data ? <LoadingRows rows={2} /> : last ? (
        <pre className="whitespace-pre-wrap rounded-xl bg-slate-50 p-4 font-sans text-sm leading-relaxed text-slate-800">{last.text.replace(/\(mock\)\s*/g, "")}</pre>
      ) : (
        <EmptyState icon={FileText} title="No report yet">Create one now to see what the owner receives each evening.</EmptyState>
      )}
    </Card>
  );
}

function Sales() {
  const [period, setPeriod] = useState("month");
  const [day, setDay] = useState(todayISO());
  const [month, setMonth] = useState(thisMonth());
  const daily = useApi("/summary/daily", { params: { date: day, language: "english" }, skip: period !== "day", ms: 120000 });
  const monthly = useApi("/summary/monthly", { params: { month, language: "english" }, skip: period !== "month", ms: 120000 });
  const s = period === "day" ? daily : monthly;
  const d = s.data;
  const maxQty = Math.max(1, ...(d?.top_products || []).map((p) => p.quantity));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented label="Period" value={period} onChange={setPeriod} options={[["day", "Day"], ["month", "Month"]]} />
        <label>
          <span className="sr-only">{period === "day" ? "Date" : "Month"}</span>
          {period === "day"
            ? <input type="date" value={day} onChange={(e) => setDay(e.target.value)} className={cx(inputCls, "w-auto")} />
            : <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className={cx(inputCls, "w-auto")} />}
        </label>
      </div>
      <ErrorNotice error={s.error} />
      {s.loading && !d ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}</div>
      ) : d && (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Stat label="Orders" icon={ShoppingBag} value={d.orders} hint={d.cancelled ? `${d.cancelled} cancelled` : "No cancellations"} />
            <Stat label="Sales" icon={TrendingUp} value={rs(d.sales)}
              delta={period === "day" ? d.sales_change_percent_vs_yesterday : d.sales_change_percent_vs_last_month}
              deltaLabel={period === "day" ? "vs yesterday" : "vs last month"} />
            <Stat label="Profit" icon={Wallet} value={rs(d.profit)} tone="success" />
            <Stat label="Average order" icon={Package} value={rs(d.average_order)} hint={d.high_risk_orders ? `${d.high_risk_orders} high-risk COD` : null} />
          </div>

          {d.note && (
            <div className="flex gap-3 rounded-2xl border border-brand-100 bg-brand-50/60 p-4 text-sm">
              <Sparkles size={18} className="mt-0.5 shrink-0 text-brand-600" aria-hidden />
              <div><p className="flex items-center gap-2 font-semibold text-brand-900">Summary <ModelChip model="nano" /></p><p className="mt-1 text-slate-700">{clean(d.note)}</p></div>
            </div>
          )}

          <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
            {period === "month" ? (
              <Card title="Daily sales and profit" icon={ChartColumn}>
                <div className="h-72" role="img" aria-label="Bar chart of daily sales and profit for the month">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={(d.daily_chart || []).map((x) => ({ ...x, day: Number(x.date.slice(8)) }))} margin={{ left: -8, right: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                      <XAxis dataKey="day" tickLine={false} axisLine={false} fontSize={12} stroke="#64748b" />
                      <YAxis tickFormatter={(v) => (v >= 1000 ? `${Math.round(v / 1000)}k` : v)} fontSize={12} width={44} tickLine={false} axisLine={false} stroke="#64748b" />
                      <Tooltip formatter={(v) => rs(v)} labelFormatter={(l) => `Day ${l}`} cursor={{ fill: "#f1f5f9" }}
                        contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 13 }} />
                      <Legend iconType="circle" wrapperStyle={{ fontSize: 13 }} />
                      <Bar dataKey="sales" name="Sales" fill="#2d63b6" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="profit" name="Profit" fill="#90b7e8" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            ) : <NightlyReport />}

            <Card title="Best sellers" icon={Package}>
              {!d.top_products?.length ? <EmptyState icon={Package} title="No sales in this period" /> : (
                <ol className="space-y-3">
                  {d.top_products.map((p, i) => (
                    <li key={p.name}>
                      <div className="flex justify-between text-sm"><span className="font-medium text-slate-800">{i + 1}. {p.name}</span><span className="tabular-nums text-slate-600">{p.quantity} sold</span></div>
                      <div className="mt-1.5 h-1.5 rounded-full bg-slate-100"><div className="h-1.5 rounded-full bg-brand-500" style={{ width: `${(p.quantity / maxQty) * 100}%` }} /></div>
                    </li>
                  ))}
                </ol>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- Advice (Ultra)
function Advice() {
  const [month, setMonth] = useState(thisMonth());
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
    <div className="space-y-6">
      <Card title="AI business advisor" icon={Brain}
        subtitle="Nemotron 3 Ultra studies this month's numbers, calculated exactly in code, and suggests what to do next."
        action={
          <div className="flex items-center gap-2">
            <label><span className="sr-only">Month</span>
              <input type="month" value={month} onChange={(e) => { setMonth(e.target.value); setData(null); }} className={cx(inputCls, "w-auto")} />
            </label>
            {data
              ? <Button variant="secondary" icon={RefreshCw} onClick={() => get(true)} loading={busy}>Ask again</Button>
              : <Button icon={Lightbulb} onClick={() => get(false)} loading={busy}>Get advice</Button>}
          </div>
        }
      >
        <ErrorNotice error={error} className="mb-4" />
        {busy ? (
          <div className="space-y-3" aria-busy="true">
            <p className="flex items-center gap-2 text-sm text-slate-600"><ModelChip model="ultra" /> Reasoning about your month. This can take up to a minute.</p>
            <Skeleton className="h-5 w-2/3" />
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}
          </div>
        ) : !data ? (
          <EmptyState icon={Lightbulb} title="Get three to five practical tips">
            Runs only when you ask, and the answer is saved, so opening it again costs nothing.
          </EmptyState>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
              {data.model_used && <ModelChip model={String(data.model_used).toLowerCase().includes("ultra") ? "ultra" : String(data.model_used).toLowerCase().includes("super") ? "super" : data.model_used} />}
              {data.cached && <Badge tone="neutral">Saved answer</Badge>}
              {data.generated_at && <span>{niceStamp(data.generated_at)}</span>}
            </div>
            {data.note && <Notice tone="warning">{data.note}</Notice>}
            {data.headline && <p className="text-base font-semibold text-slate-900">{clean(data.headline)}</p>}
            {!data.tips?.length ? <EmptyState title="No orders this month yet" /> : (
              <ol className="grid gap-3 md:grid-cols-2">
                {data.tips.map((t, i) => (
                  <li key={i} className="rounded-xl border border-slate-200 p-4">
                    <div className="flex items-start gap-3">
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-violet-50 text-sm font-bold text-violet-700">{i + 1}</span>
                      <div>
                        <p className="font-semibold text-slate-900">{t.title}</p>
                        <p className="mt-1 text-sm leading-relaxed text-slate-600">{clean(t.detail)}</p>
                        {t.based_on && <p className="mt-2 text-xs text-slate-400">Based on {t.based_on}</p>}
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- Market prices (Tavily)
const VERDICT = { higher: ["warning", "Above market"], lower: ["brand", "Below market"], similar: ["success", "In line with market"], not_enough_data: ["neutral", "Not enough data"] };

function PriceBar({ c }) {
  const lo = Math.min(c.low, c.your_price), hi = Math.max(c.high, c.your_price);
  const pos = (v) => `${hi === lo ? 50 : ((v - lo) / (hi - lo)) * 100}%`;
  return (
    <div className="mt-5" aria-hidden>
      <div className="relative h-2 rounded-full bg-slate-100">
        <div className="absolute h-2 rounded-full bg-brand-100" style={{ left: pos(c.low), width: `calc(${pos(c.high)} - ${pos(c.low)})` }} />
        <div className="absolute -top-1 h-4 w-0.5 bg-slate-500" style={{ left: pos(c.typical) }} />
        <div className="absolute -top-1.5 h-5 w-5 -translate-x-1/2 rounded-full border-2 border-white bg-brand-600 shadow" style={{ left: pos(c.your_price) }} />
      </div>
      <div className="mt-2 flex justify-between text-xs text-slate-500"><span>{rs(c.low)}</span><span>Typical {rs(c.typical)}</span><span>{rs(c.high)}</span></div>
    </div>
  );
}

function MarketResult({ c, onRefresh, busy }) {
  const [tone, label] = VERDICT[c.verdict] || VERDICT.not_enough_data;
  const sample = !String(c.search).startsWith("tavily");
  return (
    <Card title={c.product} subtitle={`Checked ${niceStamp(c.checked_at)}`}
      action={<Button size="sm" variant="ghost" icon={RefreshCw} onClick={onRefresh} disabled={busy}>Check again</Button>}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={tone} dot>{label}</Badge>
        {sample && <Badge tone="neutral">Sample results</Badge>}
      </div>
      {c.verdict !== "not_enough_data" && (
        <>
          <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[["Your price", rs(c.your_price)], ["Typical", rs(c.typical)], ["Range", `${rs(c.low)} – ${rs(c.high)}`], ["Difference", `${c.difference_percent > 0 ? "+" : ""}${c.difference_percent}%`]].map(([k, v]) => (
              <div key={k}><dt className="text-xs text-slate-500">{k}</dt><dd className="mt-0.5 text-base font-semibold text-slate-900">{v}</dd></div>
            ))}
          </dl>
          <PriceBar c={c} />
        </>
      )}
      <p className="mt-4 text-sm text-slate-700">{c.message}</p>
      {c.note && !c.note.startsWith("(mock)") && <p className="mt-1 text-sm text-slate-500">{c.note}</p>}
      <details className="mt-4 text-sm">
        <summary className="cursor-pointer font-medium text-slate-600 hover:text-slate-900">Sources ({c.sources.length})</summary>
        <ul className="mt-2 space-y-1.5">
          {c.sources.map((s, i) => (
            <li key={i} className="flex items-center gap-2">
              <a href={s.url} target="_blank" rel="noreferrer" className="inline-flex min-w-0 items-center gap-1 truncate text-brand-700 hover:underline">
                <span className="truncate">{s.title || s.url}</span><ExternalLink size={12} className="shrink-0" aria-hidden />
              </a>
              {c.prices.filter((p) => p.source === i).map((p, j) => <span key={j} className="shrink-0 text-xs text-slate-500">{rs(p.price)}</span>)}
            </li>
          ))}
        </ul>
      </details>
    </Card>
  );
}

function Market({ health }) {
  const toast = useToast();
  const setup = useApi("/setup", { ms: 0 });
  const saved = useApi("/market/checks", { ms: 0 });
  const [pid, setPid] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(productId, refresh = false) {
    if (!productId) return;
    setBusy(true);
    try {
      await api("/market/check", { method: "POST", body: { product_id: productId, refresh } });
      await saved.reload();
    } catch (e) {
      toast(e.message, "danger");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card title="What do other shops charge?" icon={Search}
        subtitle="Tavily searches the web for the product in your city, Nemotron Super reads the prices, and the app compares them with yours.">
        {health && !health.tavily && (
          <Notice tone="info" className="mb-4">Web search isn't connected yet, so results below are labelled samples.</Notice>
        )}
        <div className="flex flex-col gap-3 sm:flex-row">
          <label className="flex-1"><span className="sr-only">Product</span>
            <select value={pid} onChange={(e) => setPid(e.target.value)} className={inputCls}>
              <option value="">Choose a product…</option>
              {(setup.data?.products || []).map((p) => <option key={p.id} value={p.id}>{p.name} · {rs(p.price)}</option>)}
            </select>
          </label>
          <Button icon={Search} onClick={() => run(pid)} loading={busy} disabled={!pid}>Check market price</Button>
        </div>
        <p className="mt-3 text-xs text-slate-500">Results are saved for 24 hours and used in the monthly business advice.</p>
      </Card>
      {saved.loading && !saved.data ? <LoadingRows /> : !saved.data?.length ? (
        <EmptyState icon={Search} title="No price checks yet">Choose a product above to compare your price with the market.</EmptyState>
      ) : (
        <div className="grid gap-6 xl:grid-cols-2">
          {saved.data.map((c) => <MarketResult key={c.product_id} c={c} busy={busy} onRefresh={() => run(c.product_id, true)} />)}
        </div>
      )}
    </div>
  );
}

export default function Insights({ params, go, health }) {
  const tab = ["sales", "advice", "market"].includes(params.tab) ? params.tab : "sales";
  return (
    <div className="space-y-6">
      <Tabs value={tab} onChange={(t) => go("insights", t === "sales" ? {} : { tab: t })} tabs={[
        { id: "sales", label: "Sales", icon: ChartColumn },
        { id: "advice", label: "Business advice", icon: Brain },
        { id: "market", label: "Market prices", icon: Search },
      ]} />
      {tab === "sales" && <Sales />}
      {tab === "advice" && <Advice />}
      {tab === "market" && <Market health={health} />}
    </div>
  );
}
