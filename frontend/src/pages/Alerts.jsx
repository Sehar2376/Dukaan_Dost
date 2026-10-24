import { useState } from "react";
import { api, niceStamp, useApi } from "../api.js";
import { Button, Card, Empty, ErrorBox, FlagBadge, Loading } from "../components/ui.jsx";

export default function Alerts({ go }) {
  const { data, error, loading, reload } = useApi("/flags");
  const [busy, setBusy] = useState(null);

  async function resolve(id) {
    setBusy(id);
    try {
      await api(`/flags/${id}/resolve`, { method: "POST" });
      await reload();
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card title={`Alerts${data ? ` (${data.length})` : ""}`}>
      <ErrorBox error={error} />
      <p className="mb-3 text-xs text-slate-500">
        The assistant raises an alert for complaints, questions it can't answer, high-risk cash-on-delivery orders,
        large orders and abusive messages. Open the chat to reply yourself, then mark it done.
      </p>
      {loading && !data ? <Loading /> : !data?.length ? <Empty>No open alerts. 🎉</Empty> : (
        <ul className="space-y-2">
          {data.map((f) => (
            <li key={f.id} className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-slate-200 p-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <FlagBadge type={f.type} />
                  <span className="text-xs text-slate-500">{f.phone_masked} · {niceStamp(f.created_at)}</span>
                </div>
                <div className="mt-1 text-sm text-slate-700">{f.reason}</div>
              </div>
              <div className="flex gap-2">
                <Button kind="ghost" onClick={() => go("chats", f.customer_phone)}>Open chat</Button>
                <Button kind="dark" onClick={() => resolve(f.id)} disabled={busy === f.id}>Mark done</Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
