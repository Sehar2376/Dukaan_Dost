// Settings: shop setup (menu, prices, limits) and AI usage, costs and system status.
import { useState } from "react";
import {
  Bot, Coins, Database, Gauge, MessageCircle, RotateCcw, Search, Settings2, ShieldCheck, Sparkles, Store, Upload, Zap,
} from "../components/icons.jsx";
import { api, rs, useApi } from "../api.js";
import {
  Badge, Button, Card, EmptyState, ErrorNotice, Field, LoadingRows, ModelChip, Notice, Stat, Table, Tabs, cx, inputCls, td, useToast,
} from "../components/ui.jsx";

// ---------------------------------------------------------------- Shop setup
const EXAMPLE = `Amna's Kitchen, Karachi. Timings 11am se 10pm, Friday off.
Chicken biryani full deg 9000 (cost 6200) max 5% off
Chicken karahi 1kg 2400 cost 1500, 10% tak discount
Zarda 1kg 1200
Delivery 250 in Gulshan, Johar, Nazimabad. COD aur JazzCash. Order 1 din pehle.`;

function ShopSetup() {
  const toast = useToast();
  const current = useApi("/setup", { ms: 0 });
  const [text, setText] = useState("");
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function parse() {
    setBusy(true);
    setError(null);
    try {
      const parsed = await api("/setup/parse", { method: "POST", body: { text } });
      const now = current.data?.shop || {};
      // keep the owner's current loyalty reward unless they change it below
      parsed.shop = { loyalty_every: now.loyalty_every ?? 5, loyalty_percent: now.loyalty_percent ?? 10, ...parsed.shop };
      setDraft(parsed);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const edit = (i, field, value) => setDraft((d) => ({ ...d, products: d.products.map((p, j) => (j === i ? { ...p, [field]: value } : p)) }));

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const products = draft.products.map((p) => ({
        ...p,
        price: Number(p.price),
        cost_price: p.cost_price === "" || p.cost_price === null ? null : Number(p.cost_price),
        max_discount_percent: Number(p.max_discount_percent || 0),
        in_stock: !!p.in_stock,
      }));
      const r = await api("/setup/save", { method: "POST", body: { shop: draft.shop, products, faqs: draft.faqs || [] } });
      toast(`Saved ${r.products} products and ${r.faqs} answers. The assistant now uses your new menu.`);
      setDraft(null);
      setText("");
      current.reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function restore() {
    if (!window.confirm("Replace your menu with the sample bakery menu?")) return;
    setBusy(true);
    try {
      await api("/admin/reset-demo", { method: "POST" });
      toast("Sample bakery menu restored.");
      current.reload();
    } catch (e) {
      toast(e.message, "danger");
    } finally {
      setBusy(false);
    }
  }

  const shop = current.data?.shop;
  const small = "w-24 rounded-md border border-slate-300 px-2 py-1 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20";

  return (
    <div className="space-y-6">
      <Card title="Set up your shop in five minutes" icon={Upload}
        subtitle="Paste your menu, prices, cost prices, discount limits, timings and delivery areas in any language. Nemotron Super turns it into a product list for you to check.">
        <label htmlFor="setup-text" className="sr-only">Shop details</label>
        <textarea id="setup-text" value={text} onChange={(e) => setText(e.target.value)} rows={7} maxLength={8000} placeholder={EXAMPLE}
          className={cx(inputCls, "font-mono text-[13px] leading-relaxed")} dir="auto" />
        <div className="mt-3 flex flex-wrap gap-2">
          <Button icon={Sparkles} onClick={parse} loading={busy && !draft} disabled={!text.trim()}>Read my menu</Button>
          <Button variant="secondary" onClick={() => setText(EXAMPLE)} disabled={busy}>Use an example</Button>
        </div>
        <ErrorNotice error={error} className="mt-4" />
      </Card>

      {draft && (
        <Card title="Check and save" subtitle="Fix anything the AI got wrong, then save." icon={ShieldCheck}
          action={<Button onClick={save} loading={busy}>Save and go live</Button>}>
          {draft.warnings?.length > 0 && (
            <Notice tone="warning" title="Please check" className="mb-4"><ul className="list-disc pl-4">{draft.warnings.map((w) => <li key={w}>{w}</li>)}</ul></Notice>
          )}
          <div className="mb-5 grid gap-4 md:grid-cols-2">
            <Field label="Shop name"><input value={draft.shop?.name || ""} onChange={(e) => setDraft({ ...draft, shop: { ...draft.shop, name: e.target.value } })} className={inputCls} /></Field>
            <Field label="Delivery fee (Rs)"><input type="number" value={draft.shop?.delivery_fee ?? 0} onChange={(e) => setDraft({ ...draft, shop: { ...draft.shop, delivery_fee: Number(e.target.value) } })} className={inputCls} /></Field>
            <Field label="Loyalty reward: every Nth order (0 = off)"><input type="number" min="0" max="50" value={draft.shop?.loyalty_every ?? 5} onChange={(e) => setDraft({ ...draft, shop: { ...draft.shop, loyalty_every: Number(e.target.value) } })} className={inputCls} /></Field>
            <Field label="Loyalty reward discount (%)"><input type="number" min="0" max="30" value={draft.shop?.loyalty_percent ?? 10} onChange={(e) => setDraft({ ...draft, shop: { ...draft.shop, loyalty_percent: Number(e.target.value) } })} className={inputCls} /></Field>
            <p className="text-sm text-slate-600"><span className="text-slate-400">Timings:</span> {draft.shop?.timings || "—"}</p>
            <p className="text-sm text-slate-600"><span className="text-slate-400">Delivery areas:</span> {(draft.shop?.delivery_areas || []).join(", ") || "—"}</p>
          </div>
          <Table head={["Product", "Price (Rs)", "Cost (Rs)", "Max discount %", "In stock"]}>
            {draft.products.map((p, i) => (
              <tr key={i}>
                <td className={td}><input aria-label="Product name" value={p.name} onChange={(e) => edit(i, "name", e.target.value)} className={cx(small, "w-full min-w-[180px]")} /></td>
                <td className={td}><input aria-label="Price" type="number" value={p.price ?? ""} onChange={(e) => edit(i, "price", e.target.value)} className={small} /></td>
                <td className={td}><input aria-label="Cost price" type="number" value={p.cost_price ?? ""} placeholder="missing" onChange={(e) => edit(i, "cost_price", e.target.value)}
                  className={cx(small, (p.cost_price == null || p.cost_price === "") && "border-amber-400 bg-amber-50")} /></td>
                <td className={td}><input aria-label="Maximum discount percent" type="number" value={p.max_discount_percent ?? 0} onChange={(e) => edit(i, "max_discount_percent", e.target.value)} className={cx(small, "w-20")} /></td>
                <td className={td}><input aria-label="In stock" type="checkbox" checked={!!p.in_stock} onChange={(e) => edit(i, "in_stock", e.target.checked)} className="h-4 w-4 accent-brand-600" /></td>
              </tr>
            ))}
          </Table>
        </Card>
      )}

      <Card title="Current menu" icon={Store} subtitle={shop ? `${shop.name} · ${shop.timings || ""} · Delivery ${rs(shop.delivery_fee)}${(shop.loyalty_every ?? 5) >= 2 && (shop.loyalty_percent ?? 10) > 0 ? ` · Loyalty: every ${shop.loyalty_every ?? 5}th order ${shop.loyalty_percent ?? 10}% off` : ""}` : null}
        action={<Button size="sm" variant="ghost" icon={RotateCcw} onClick={restore} disabled={busy}>Restore sample menu</Button>}>
        {current.loading && !current.data ? <LoadingRows /> : !current.data?.products?.length ? <EmptyState title="No products yet" /> : (
          <Table head={["Product", "Price", "Cost", "Max discount", "Stock"]}>
            {current.data.products.map((p) => (
              <tr key={p.id}>
                <td className={cx(td, "font-medium text-slate-900")}>{p.name}</td>
                <td className={cx(td, "tabular-nums")}>{rs(p.price)}</td>
                <td className={cx(td, "tabular-nums text-slate-500")}>{rs(p.cost_price)}</td>
                <td className={cx(td, "tabular-nums")}>{p.max_discount_percent}%</td>
                <td className={td}>{p.in_stock ? <Badge tone="success" dot>In stock</Badge> : <Badge tone="danger" dot>Out of stock</Badge>}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- AI & usage
const usd = (n) => "$" + (Number(n) || 0).toFixed(4);

function StatusRow({ icon: Icon, label, on, onText, offText, detail }) {
  return (
    <li className="flex items-start justify-between gap-4 py-3">
      <div className="flex items-start gap-3">
        <Icon size={17} className="mt-0.5 text-slate-400" aria-hidden />
        <div><p className="text-sm font-medium text-slate-900">{label}</p>{detail && <p className="text-xs text-slate-500">{detail}</p>}</div>
      </div>
      <Badge tone={on ? "success" : "neutral"} dot>{on ? onText : offText}</Badge>
    </li>
  );
}

function AIUsage({ health, refreshFlags }) {
  const toast = useToast();
  const { data, error, loading, reload } = useApi("/usage");
  const [busy, setBusy] = useState(false);

  async function loadSample() {
    if (!window.confirm("Replace all orders, customers, chats and alerts with the sample shop data?")) return;
    setBusy(true);
    try {
      const r = await api("/admin/load-demo", { method: "POST" });
      toast(`Sample shop loaded: ${r.orders} orders and ${r.customers} customers.`);
      reload();
      refreshFlags?.();
    } catch (e) {
      toast(e.message, "danger");
    } finally {
      setBusy(false);
    }
  }

  const models = data ? [["nano", "Every message: language, intent, quick answers"], ["super", "Orders, bargaining, menu reading, price reading"], ["ultra", "Monthly business advice, on request"]] : [];
  const maxCalls = Math.max(1, ...models.map(([k]) => data?.by_model?.[k]?.calls || 0));
  const actual = data?.estimated_cost_usd || 0;
  const baseline = data?.baseline_all_ultra_usd || 0;
  const saving = baseline > 0 ? Math.round((1 - actual / baseline) * 100) : null;

  return (
    <div className="space-y-6">
      {health && (
        <Card title="System status" icon={Settings2}>
          <ul className="-my-3 divide-y divide-slate-100">
            <StatusRow icon={Bot} label="AI models" on={!health.mock_ai} onText="Live" offText="Practice mode"
              detail={health.mock_ai ? "Add the Nebius API key on the server to switch on Nemotron." : "NVIDIA Nemotron Nano, Super and Ultra on Nebius Token Factory"} />
            <StatusRow icon={Database} label="Database" on={health.firestore} onText="Firestore" offText="Temporary"
              detail={health.firestore ? "Data is saved permanently." : "Data resets when the server restarts."} />
            <StatusRow icon={Search} label="Market price search" on={health.tavily} onText="Tavily connected" offText="Sample results" />
            <StatusRow icon={MessageCircle} label="WhatsApp" on={health.whatsapp} onText="Connected" offText="Web chat only" />
          </ul>
        </Card>
      )}

      <ErrorNotice error={error} />
      {loading && !data ? <LoadingRows rows={4} /> : data && (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Stat label="Messages today" icon={MessageCircle} value={data.messages} hint={`Limit ${data.limits.total_per_day} per day`} />
            <Stat label="AI calls today" icon={Zap} value={data.ai_calls} />
            <Stat label="Tokens today" icon={Gauge} value={(data.prompt_tokens + data.completion_tokens).toLocaleString()} />
            <Stat label="Cost today" icon={Coins} value={usd(actual)} hint={`Budget $${data.limits.daily_budget_usd} per day`} tone={actual >= data.limits.daily_budget_usd ? "danger" : "neutral"} />
          </div>

          <Card title="Smart model routing" icon={Sparkles} subtitle="Each task goes to the smallest Nemotron model that can do it well.">
            <ul className="space-y-4">
              {models.map(([k, what]) => {
                const m = data.by_model?.[k] || { calls: 0, cost_usd: 0 };
                return (
                  <li key={k}>
                    <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                      <span className="flex items-center gap-2"><ModelChip model={k} /><span className="text-slate-600">{what}</span></span>
                      <span className="tabular-nums text-slate-700">{m.calls} calls · {usd(m.cost_usd)}</span>
                    </div>
                    <div className="mt-1.5 h-1.5 rounded-full bg-slate-100">
                      <div className={cx("h-1.5 rounded-full", { nano: "bg-sky-500", super: "bg-brand-600", ultra: "bg-violet-500" }[k])} style={{ width: `${(m.calls / maxCalls) * 100}%` }} />
                    </div>
                  </li>
                );
              })}
            </ul>
            <div className="mt-5 grid gap-4 rounded-xl bg-slate-50 p-4 sm:grid-cols-3">
              <div><p className="text-xs text-slate-500">Cost today with routing</p><p className="mt-0.5 text-lg font-bold text-slate-900">{usd(actual)}</p></div>
              <div><p className="text-xs text-slate-500">Same work, Ultra for everything</p><p className="mt-0.5 text-lg font-bold text-slate-900">{usd(baseline)}</p></div>
              <div><p className="text-xs text-slate-500">Saved by routing</p><p className="mt-0.5 text-lg font-bold text-emerald-700">{saving === null ? "—" : `${saving}%`}</p></div>
            </div>
            {data.ai_calls === 0 && <p className="mt-3 text-xs text-slate-500">No AI calls yet today. Numbers appear after the first live message.</p>}
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Credit protection" icon={ShieldCheck}>
              <ul className="space-y-2.5 text-sm text-slate-700">
                <li>Up to <b>{data.limits.per_phone_per_day}</b> messages per customer per day</li>
                <li>Up to <b>{data.limits.total_per_day}</b> messages for the whole shop per day</li>
                <li>The assistant pauses after <b>${data.limits.daily_budget_usd}</b> of estimated AI spend in a day, and alerts the owner</li>
                <li>Up to <b>{data.limits.tavily_per_day}</b> market searches per day; each result is reused for 24 hours</li>
                <li>Today: <b>{data.tavily_searches ?? 0}</b> market searches</li>
              </ul>
            </Card>
            <Card title="Previous days" icon={Gauge}>
              {!data.history?.length ? <EmptyState title="No history yet" /> : (
                <Table minWidth={320} head={["Date", "Messages", "Cost"]}>
                  {data.history.map((h) => (
                    <tr key={h.date}><td className={td}>{h.date}</td><td className={cx(td, "tabular-nums")}>{h.messages}</td><td className={cx(td, "tabular-nums")}>{usd(h.estimated_cost_usd)}</td></tr>
                  ))}
                </Table>
              )}
            </Card>
          </div>
        </>
      )}

      <Card title="Sample data" icon={Database} subtitle="A Karachi home bakery with 20 customers and about three months of orders, clearly labelled as sample data."
        action={<Button variant="secondary" onClick={loadSample} loading={busy}>Load sample shop</Button>}>
        <p className="text-sm text-slate-500">Loading replaces the current orders, customers, chats and alerts.</p>
      </Card>
    </div>
  );
}

export default function Settings({ params, go, health, refreshFlags }) {
  const tab = params.tab === "ai" ? "ai" : "shop";
  return (
    <div className="space-y-6">
      <Tabs value={tab} onChange={(t) => go("settings", t === "ai" ? { tab: t } : {})} tabs={[
        { id: "shop", label: "Shop setup", icon: Store },
        { id: "ai", label: "AI and usage", icon: Bot },
      ]} />
      {tab === "shop" ? <ShopSetup /> : <AIUsage health={health} refreshFlags={refreshFlags} />}
    </div>
  );
}
