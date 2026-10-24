// Orders (with the cash-on-delivery risk check) and bookings.
import { useEffect, useState } from "react";
import { CalendarDays, Info, Search, ShoppingBag } from "../components/icons.jsx";
import { api, niceStamp, niceTime, rs, useApi } from "../api.js";
import {
  Badge, Button, Card, EmptyState, ErrorNotice, LoadingRows, RiskBadge, Segmented, Table, Tabs, cx, inputCls, store, td, useToast,
} from "../components/ui.jsx";

const STATUSES = ["new", "confirmed", "delivered", "cancelled"];
const STATUS_STYLE = {
  new: "border-brand-200 bg-brand-50 text-brand-800",
  confirmed: "border-violet-200 bg-violet-50 text-violet-800",
  delivered: "border-emerald-200 bg-emerald-50 text-emerald-800",
  cancelled: "border-slate-200 bg-slate-100 text-slate-600",
};

function OrdersTable() {
  const toast = useToast();
  const [status, setStatus] = useState("");
  const [risk, setRisk] = useState("all");
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(50);
  const { data, error, loading, reload } = useApi("/orders", { params: { status } });
  const [saving, setSaving] = useState(null);

  const rows = (data || [])
    .filter((o) => risk === "all" || o.risk_level === risk)
    .filter((o) => !q || `${o.customer_name} ${o.phone_masked} ${o.address}`.toLowerCase().includes(q.toLowerCase()));
  const highRisk = (data || []).filter((o) => o.risk_level === "high" && o.status === "new").length;

  async function changeStatus(id, s) {
    setSaving(id);
    try {
      await api(`/orders/${id}`, { method: "PATCH", body: { status: s } });
      await reload();
      toast(`Order marked as ${s}.`);
    } catch (e) {
      toast(e.message, "danger");
    } finally {
      setSaving(null);
    }
  }

  return (
    <Card bodyClass="p-5">
      <div className="flex flex-wrap items-center gap-3">
        <label className="relative min-w-[200px] flex-1">
          <span className="sr-only">Search orders</span>
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name, phone or address" className={cx(inputCls, "pl-9")} />
        </label>
        <label>
          <span className="sr-only">Status</span>
          <select value={status} onChange={(e) => setStatus(e.target.value)} className={cx(inputCls, "w-auto capitalize")}>
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <Segmented label="Risk" value={risk} onChange={setRisk} options={[["all", "All"], ["high", "High risk"], ["medium", "Medium"], ["low", "Low"]]} />
      </div>

      {highRisk > 0 && (
        <p className="mt-4 flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
          <Info size={15} aria-hidden /> {highRisk} new cash-on-delivery {highRisk === 1 ? "order looks" : "orders look"} risky. Call the customer or ask for advance payment before sending.
        </p>
      )}

      <ErrorNotice error={error} className="mt-4" />
      <div className="mt-4">
        {loading && !data ? <LoadingRows rows={6} /> : rows.length === 0 ? (
          <EmptyState icon={ShoppingBag} title="No orders found">Try a different filter, or place an order from the customer chat.</EmptyState>
        ) : (
          <Table minWidth={900} head={["Customer", "Items", "Total", "Delivery", "Risk check", "Status"]}>
            {rows.slice(0, limit).map((o) => (
              <tr key={o.id} className="hover:bg-slate-50/60">
                <td className={td}>
                  <p className="font-medium text-slate-900">{o.customer_name || "—"}</p>
                  <p className="text-xs text-slate-500">{o.phone_masked}</p>
                  <p className="text-xs text-slate-400">{niceStamp(o.created_at)}</p>
                </td>
                <td className={cx(td, "text-slate-700")}>{o.items.map((i) => <p key={i.product_id}>{i.quantity} × {i.name}</p>)}</td>
                <td className={td}>
                  <p className="font-semibold text-slate-900">{rs(o.total)}</p>
                  {o.discount > 0 && <p className="text-xs text-emerald-700">{rs(o.discount)} discount</p>}
                  <p className="text-xs text-slate-500">{o.payment_type === "cod" ? "Cash on delivery" : o.payment_type}</p>
                </td>
                <td className={cx(td, "max-w-[220px]")}>
                  <p className="text-slate-700">{niceTime(o.delivery_time)}</p>
                  <p className="truncate text-xs text-slate-500" title={o.address}>{o.address}</p>
                </td>
                <td className={cx(td, "max-w-[230px]")}>
                  <RiskBadge level={o.risk_level} />
                  {o.risk_level !== "low" && (o.risk_reasons || []).length > 0 && (
                    <ul className="mt-1.5 space-y-0.5 text-xs text-slate-500">{o.risk_reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                  )}
                </td>
                <td className={td}>
                  <label>
                    <span className="sr-only">Order status</span>
                    <select value={o.status} disabled={saving === o.id} onChange={(e) => changeStatus(o.id, e.target.value)}
                      className={cx("rounded-lg border px-2.5 py-1.5 text-[13px] font-medium capitalize focus:outline-none focus:ring-2 focus:ring-brand-500/30", STATUS_STYLE[o.status])}>
                      {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </label>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </div>
      {rows.length > limit && (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
          <span>Showing {limit} of {rows.length}</span>
          <Button size="sm" variant="secondary" onClick={() => setLimit((l) => l + 50)}>Show more</Button>
        </div>
      )}
      <p className="mt-4 text-xs text-slate-500">
        The risk check uses rules in code: address detail, order size, and the customer's past deliveries and cancellations.
        Marking an order delivered or cancelled updates how much that customer is trusted next time.
      </p>
    </Card>
  );
}

function Bookings() {
  const { data, error, loading } = useApi("/bookings");
  return (
    <Card bodyClass="p-5">
      <ErrorNotice error={error} />
      {loading && !data ? <LoadingRows /> : !data?.length ? (
        <EmptyState icon={CalendarDays} title="No bookings yet">Customers can ask in the chat, for example "Saturday 5 baje tasting book kar dein".</EmptyState>
      ) : (
        <Table head={["When", "Service", "Customer", "Status", "Booked"]}>
          {data.map((b) => (
            <tr key={b.id}>
              <td className={cx(td, "font-medium text-slate-900")}>{niceTime(b.date_time)}</td>
              <td className={td}>{b.service}</td>
              <td className={td}>{b.customer_name || "—"}<p className="text-xs text-slate-500">{b.phone_masked}</p></td>
              <td className={td}><Badge tone={b.status === "cancelled" ? "neutral" : "success"} dot className="capitalize">{b.status}</Badge></td>
              <td className={cx(td, "text-xs text-slate-500")}>{niceStamp(b.created_at)}</td>
            </tr>
          ))}
        </Table>
      )}
    </Card>
  );
}

export default function Orders({ params, go }) {
  const tab = params.tab === "bookings" ? "bookings" : "orders";
  useEffect(() => { store.set("dd_seen_orders", true); }, []);
  return (
    <div className="space-y-6">
      <Tabs value={tab} onChange={(t) => go("orders", t === "bookings" ? { tab: t } : {})} tabs={[
        { id: "orders", label: "Orders", icon: ShoppingBag },
        { id: "bookings", label: "Bookings", icon: CalendarDays },
      ]} />
      {tab === "orders" ? <OrdersTable /> : <Bookings />}
    </div>
  );
}
