// Market price check: Tavily web search -> Nemotron Super reads prices -> Python compares with your price.
import { useState } from "react";
import { api, niceStamp, rs, useApi } from "../api.js";
import { Badge, Button, Card, Empty, ErrorBox, Loading } from "../components/ui.jsx";

const VERDICT = {
  higher: ["amber", "Above market"],
  lower: ["blue", "Below market"],
  similar: ["green", "Close to market"],
  not_enough_data: ["slate", "Not enough data"],
};

function PriceBar({ c }) {
  // Where your price sits between the lowest and highest market price
  const lo = Math.min(c.low, c.your_price);
  const hi = Math.max(c.high, c.your_price);
  const pos = (v) => `${hi === lo ? 50 : ((v - lo) / (hi - lo)) * 100}%`;
  return (
    <div className="mt-4 mb-6">
      <div className="relative h-2 rounded-full bg-slate-100">
        <div className="absolute h-2 rounded-full bg-green-200" style={{ left: pos(c.low), width: `calc(${pos(c.high)} - ${pos(c.low)})` }} />
        <div className="absolute -top-1 h-4 w-1 rounded bg-slate-500" style={{ left: pos(c.typical) }} title="Typical" />
        <div className="absolute -top-1.5 h-5 w-5 -translate-x-1/2 rounded-full border-2 border-white bg-green-600 shadow" style={{ left: pos(c.your_price) }} title="Your price" />
      </div>
      <div className="mt-2 flex justify-between text-xs text-slate-500">
        <span>Low {rs(c.low)}</span>
        <span>Typical {rs(c.typical)}</span>
        <span>High {rs(c.high)}</span>
      </div>
    </div>
  );
}

function Result({ c, onRefresh, busy }) {
  const [color, label] = VERDICT[c.verdict] || VERDICT.not_enough_data;
  const sample = !c.search.startsWith("tavily");
  return (
    <Card
      title={c.product}
      action={<Button kind="ghost" onClick={onRefresh} disabled={busy}>Search again</Button>}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge color={color}>{label}</Badge>
        {sample && <Badge color="amber">Sample results (no Tavily key)</Badge>}
        {c.cached && <Badge color="slate">Saved result</Badge>}
        <span className="text-xs text-slate-500">Checked {niceStamp(c.checked_at)}</span>
      </div>
      {c.verdict !== "not_enough_data" ? (
        <>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div><div className="text-xs text-slate-500">Your price</div><div className="text-lg font-bold">{rs(c.your_price)}</div></div>
            <div><div className="text-xs text-slate-500">Typical</div><div className="text-lg font-bold">{rs(c.typical)}</div></div>
            <div><div className="text-xs text-slate-500">Range</div><div className="text-lg font-bold">{rs(c.low)}–{rs(c.high)}</div></div>
            <div><div className="text-xs text-slate-500">Difference</div><div className="text-lg font-bold">{c.difference_percent > 0 ? "+" : ""}{c.difference_percent}%</div></div>
          </div>
          <PriceBar c={c} />
        </>
      ) : null}
      <p className="text-sm text-slate-700">{c.message}</p>
      {c.note && <p className="mt-1 text-sm text-slate-600">{c.note}</p>}
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-slate-500">Where these prices came from ({c.sources.length} results)</summary>
        <ul className="mt-2 space-y-1">
          {c.sources.map((s, i) => (
            <li key={i} className="truncate">
              <span className="text-slate-400">[{i}]</span>{" "}
              <a href={s.url} target="_blank" rel="noreferrer" className="text-green-700 underline">{s.title || s.url}</a>
              {c.prices.filter((p) => p.source === i).map((p, j) => (
                <span key={j} className="ml-1 text-slate-600">· {rs(p.price)}</span>
              ))}
            </li>
          ))}
        </ul>
        <div className="mt-2 text-xs text-slate-400">Search: “{c.query}” · read by {c.model_used}</div>
      </details>
    </Card>
  );
}

export default function Market() {
  const setup = useApi("/setup", { ms: 0 });
  const saved = useApi("/market/checks", { ms: 0 });
  const health = useApi("/", { ms: 0 });
  const [pid, setPid] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function run(productId, refresh = false) {
    if (!productId) return;
    setBusy(true);
    setError(null);
    try {
      await api("/market/check", { method: "POST", body: { product_id: productId, refresh } });
      saved.reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const products = setup.data?.products || [];
  return (
    <div className="space-y-4">
      <Card title="What do other shops charge?">
        <p className="mb-3 text-sm text-slate-600">
          Pick a product. <b>Tavily</b> searches the web for its price in your city, <b>Nemotron Super</b> reads the
          results, and the app compares them with your price. Results are saved for 24 hours, and the monthly
          <b> Ultra advice</b> uses them for pricing tips.
        </p>
        {health.data && !health.data.tavily && (
          <div className="mb-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">
            No <code>TAVILY_API_KEY</code> yet, so the app uses clearly labelled <b>sample</b> results. Add a free key
            from app.tavily.com to <code>backend/.env</code> and restart the server for real web prices.
          </div>
        )}
        <div className="flex flex-col gap-2 sm:flex-row">
          <select
            value={pid}
            onChange={(e) => setPid(e.target.value)}
            className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            <option value="">Choose a product…</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>{p.name} ({rs(p.price)})</option>
            ))}
          </select>
          <Button onClick={() => run(pid)} disabled={busy || !pid}>{busy ? "Searching…" : "Check market price"}</Button>
        </div>
        <div className="mt-2"><ErrorBox error={error} /></div>
      </Card>

      {saved.loading && !saved.data ? <Loading /> : !saved.data?.length ? (
        <Empty>No price checks yet. Choose a product above.</Empty>
      ) : (
        saved.data.map((c) => <Result key={c.product_id} c={c} busy={busy} onRefresh={() => run(c.product_id, true)} />)
      )}
    </div>
  );
}
