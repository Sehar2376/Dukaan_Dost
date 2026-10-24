// 5-minute owner setup: paste the menu -> Nemotron Super turns it into a product list -> review -> save.
import { useState } from "react";
import { api, rs, useApi } from "../api.js";
import { Badge, Button, Card, Empty, ErrorBox, Loading, Table } from "../components/ui.jsx";

const EXAMPLE = `Amna's Kitchen, Karachi. Timings 11am se 10pm, Friday off.
Chicken biryani full deg 9000 (cost 6200) max 5% off
Chicken karahi 1kg 2400 cost 1500, 10% tak discount
Zarda 1kg 1200
Delivery 250 in Gulshan, Johar, Nazimabad. COD aur JazzCash. Order 1 din pehle.`;

export default function Setup() {
  const current = useApi("/setup", { ms: 0 });
  const [text, setText] = useState("");
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(null);

  async function parse() {
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      setDraft(await api("/setup/parse", { method: "POST", body: { text } }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function editProduct(i, field, value) {
    setDraft((d) => {
      const products = d.products.map((p, j) => (j === i ? { ...p, [field]: value } : p));
      return { ...d, products };
    });
  }

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
      setDone(`Saved ${r.products} products and ${r.faqs} FAQs. The assistant now answers from the new menu.`);
      setDraft(null);
      setText("");
      current.reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function resetDemo() {
    setBusy(true);
    try {
      await api("/admin/reset-demo", { method: "POST" });
      setDone("Demo bakery restored.");
      current.reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const shop = current.data?.shop;

  return (
    <div className="space-y-4">
      <Card title="Step 1 · Paste your shop details">
        <p className="mb-2 text-sm text-slate-600">
          Write or paste your menu, prices, cost prices, discount limits, timings, delivery areas and rules, in any
          language. <b>Nemotron Super</b> turns it into a product list for you to check.
        </p>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={7}
          maxLength={8000}
          placeholder={EXAMPLE}
          className="w-full rounded-xl border border-slate-300 p-3 text-sm"
        />
        <div className="mt-2 flex flex-wrap gap-2">
          <Button onClick={parse} disabled={busy || !text.trim()}>{busy && !draft ? "Reading your menu…" : "Generate with AI"}</Button>
          <Button kind="ghost" onClick={() => setText(EXAMPLE)} disabled={busy}>Use example text</Button>
        </div>
        <ErrorBox error={error} />
        {done && <div className="mt-2 rounded-xl bg-green-50 p-3 text-sm text-green-800">✅ {done}</div>}
      </Card>

      {draft && (
        <Card title="Step 2 · Check and save" action={<Button onClick={save} disabled={busy}>Save and go live</Button>}>
          {draft.warnings?.length > 0 && (
            <div className="mb-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">
              {draft.warnings.map((w) => <div key={w}>⚠️ {w}</div>)}
            </div>
          )}
          <div className="mb-3 grid gap-2 text-sm md:grid-cols-2">
            <label className="block">Shop name
              <input value={draft.shop?.name || ""} onChange={(e) => setDraft({ ...draft, shop: { ...draft.shop, name: e.target.value } })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5" />
            </label>
            <label className="block">Delivery fee (Rs)
              <input type="number" value={draft.shop?.delivery_fee ?? 0} onChange={(e) => setDraft({ ...draft, shop: { ...draft.shop, delivery_fee: Number(e.target.value) } })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5" />
            </label>
            <div className="text-slate-600">Timings: {draft.shop?.timings || "—"}</div>
            <div className="text-slate-600">Areas: {(draft.shop?.delivery_areas || []).join(", ") || "—"}</div>
          </div>
          <Table head={["Product", "Price (Rs)", "Cost (Rs)", "Max discount %", "In stock"]}>
            {draft.products.map((p, i) => (
              <tr key={i}>
                <td className="px-3 py-1.5"><input value={p.name} onChange={(e) => editProduct(i, "name", e.target.value)} className="w-full rounded border border-slate-300 px-2 py-1" /></td>
                <td className="px-3 py-1.5"><input type="number" value={p.price ?? ""} onChange={(e) => editProduct(i, "price", e.target.value)} className="w-24 rounded border border-slate-300 px-2 py-1" /></td>
                <td className="px-3 py-1.5"><input type="number" value={p.cost_price ?? ""} placeholder="missing" onChange={(e) => editProduct(i, "cost_price", e.target.value)} className={`w-24 rounded border px-2 py-1 ${p.cost_price == null || p.cost_price === "" ? "border-amber-400 bg-amber-50" : "border-slate-300"}`} /></td>
                <td className="px-3 py-1.5"><input type="number" value={p.max_discount_percent ?? 0} onChange={(e) => editProduct(i, "max_discount_percent", e.target.value)} className="w-20 rounded border border-slate-300 px-2 py-1" /></td>
                <td className="px-3 py-1.5"><input type="checkbox" checked={!!p.in_stock} onChange={(e) => editProduct(i, "in_stock", e.target.checked)} /></td>
              </tr>
            ))}
          </Table>
          {draft.faqs?.length > 0 && (
            <div className="mt-4">
              <div className="mb-1 text-sm font-semibold text-slate-700">FAQs the assistant will use</div>
              <ul className="space-y-1 text-sm">
                {draft.faqs.map((f, i) => <li key={i} className="rounded-lg bg-slate-50 p-2"><b>{f.question}</b> — {f.answer}</li>)}
              </ul>
            </div>
          )}
        </Card>
      )}

      <Card title="Current menu" action={<Button kind="ghost" onClick={resetDemo} disabled={busy}>Restore demo bakery</Button>}>
        {current.loading && !current.data ? <Loading /> : !current.data?.products?.length ? <Empty>No products.</Empty> : (
          <>
            <div className="mb-3 flex flex-wrap gap-2 text-sm text-slate-600">
              <Badge color="green">{shop?.name}</Badge>
              <span>{shop?.timings}</span>
              <span>· Delivery {rs(shop?.delivery_fee)}</span>
            </div>
            <Table head={["Product", "Price", "Cost", "Max discount", "Stock"]}>
              {current.data.products.map((p) => (
                <tr key={p.id}>
                  <td className="px-3 py-2">{p.name}</td>
                  <td className="px-3 py-2">{rs(p.price)}</td>
                  <td className="px-3 py-2 text-slate-500">{rs(p.cost_price)}</td>
                  <td className="px-3 py-2">{p.max_discount_percent}%</td>
                  <td className="px-3 py-2">{p.in_stock ? <Badge color="green">In stock</Badge> : <Badge color="red">Out</Badge>}</td>
                </tr>
              ))}
            </Table>
          </>
        )}
      </Card>
    </div>
  );
}
