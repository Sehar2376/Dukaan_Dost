// Customers the assistant remembers: orders, deliveries, cancellations and trust level.
import { useState } from "react";
import { Search, Users } from "../components/icons.jsx";
import { useApi } from "../api.js";
import { Badge, Card, EmptyState, ErrorNotice, LoadingRows, Table, cx, inputCls, td } from "../components/ui.jsx";

function trust(c) {
  if ((c.cancelled_orders || 0) >= 2) return ["danger", "Risky"];
  if ((c.completed_orders || 0) >= 2) return ["success", "Trusted"];
  return ["neutral", "New"];
}

export default function Customers() {
  const { data, error, loading } = useApi("/customers");
  const [q, setQ] = useState("");
  const rows = [...(data || [])]
    .filter((c) => !q || `${c.name || ""} ${c.phone}`.toLowerCase().includes(q.toLowerCase()))
    .sort((a, b) => (b.total_orders || 0) - (a.total_orders || 0));

  return (
    <Card bodyClass="p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-500">
          Returning customers are greeted by name and offered their last order. Phone numbers are always masked.
        </p>
        <label className="relative w-full sm:w-72">
          <span className="sr-only">Search customers</span>
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search customers" className={cx(inputCls, "pl-9")} />
        </label>
      </div>
      <ErrorNotice error={error} className="mt-4" />
      <div className="mt-4">
        {loading && !data ? <LoadingRows rows={6} /> : !rows.length ? (
          <EmptyState icon={Users} title="No customers yet">Customers appear here after their first order.</EmptyState>
        ) : (
          <Table head={["Customer", "Orders", "Delivered", "Cancelled", "Trust", "Saved address"]}>
            {rows.map((c) => {
              const [tone, label] = trust(c);
              return (
                <tr key={c.id} className="hover:bg-slate-50/60">
                  <td className={td}><p className="font-medium text-slate-900">{c.name || "—"}</p><p className="text-xs text-slate-500">{c.phone}</p></td>
                  <td className={cx(td, "tabular-nums")}>{c.total_orders || 0}</td>
                  <td className={cx(td, "tabular-nums")}>{c.completed_orders || 0}</td>
                  <td className={cx(td, "tabular-nums")}>{c.cancelled_orders || 0}</td>
                  <td className={td}><Badge tone={tone} dot>{label}</Badge></td>
                  <td className={cx(td, "max-w-[280px] truncate text-slate-500")} title={(c.addresses || [])[0]}>{(c.addresses || [])[0] || "—"}</td>
                </tr>
              );
            })}
          </Table>
        )}
      </div>
    </Card>
  );
}
