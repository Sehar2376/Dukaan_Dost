// Owner view of all chats: read, take over from the AI, reply, hand back.
import { useEffect, useState } from "react";
import { api, niceStamp, useApi } from "../api.js";
import { Badge, Button, Card, Empty, ErrorBox, Loading } from "../components/ui.jsx";

export default function Chats({ chatPhone }) {
  const list = useApi("/conversations");
  const [phone, setPhone] = useState(chatPhone || null);
  const conv = useApi(phone ? `/conversations/${encodeURIComponent(phone)}` : "/", { skip: !phone, ms: 15000 });
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (chatPhone) setPhone(chatPhone);
  }, [chatPhone]);

  async function takeover(paused) {
    setBusy(true);
    setErr(null);
    try {
      await api(`/conversations/${encodeURIComponent(phone)}/takeover`, { method: "POST", params: { paused } });
      await Promise.all([conv.reload(), list.reload()]);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function sendReply(e) {
    e.preventDefault();
    if (!reply.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await api(`/conversations/${encodeURIComponent(phone)}/reply`, { method: "POST", body: { text: reply.trim() } });
      setReply("");
      if (!r.sent_to_whatsapp && phone.startsWith("+")) setErr("Saved, but not sent to WhatsApp (Twilio not set up on the backend).");
      await conv.reload();
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  const c = phone ? conv.data : null;

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <Card title="Chats">
        <ErrorBox error={list.error} />
        {list.loading && !list.data ? <Loading /> : !list.data?.length ? <Empty>No chats yet. Try the Customer chat page.</Empty> : (
          <ul className="max-h-[65vh] space-y-1 overflow-y-auto">
            {list.data.map((x) => (
              <li key={x.phone}>
                <button
                  onClick={() => setPhone(x.phone)}
                  className={`w-full rounded-xl p-3 text-left transition ${phone === x.phone ? "bg-green-50" : "hover:bg-slate-50"}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-slate-800">{x.phone_masked}</span>
                    {x.ai_paused ? <Badge color="amber">You're replying</Badge> : <Badge color="green">AI</Badge>}
                  </div>
                  <div className="mt-0.5 truncate text-xs text-slate-500">{x.last_message?.text || "—"}</div>
                  <div className="text-xs text-slate-400">{niceStamp(x.updated_at)}</div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card
        title={c ? `Chat with ${c.phone_masked}` : "Select a chat"}
        action={
          c && (c.ai_paused ? (
            <Button kind="primary" onClick={() => takeover(false)} disabled={busy}>Hand back to AI</Button>
          ) : (
            <Button kind="dark" onClick={() => takeover(true)} disabled={busy}>Take over</Button>
          ))
        }
      >
        <ErrorBox error={err || conv.error} />
        {!phone ? <Empty>Pick a chat on the left.</Empty> : !c ? <Loading /> : (
          <>
            {c.ai_paused && (
              <div className="mb-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">
                The AI is paused for this customer. Your replies go straight to them. Hand back to the AI when done.
              </div>
            )}
            <div className="chat-bg max-h-[55vh] space-y-2 overflow-y-auto rounded-xl p-3">
              {(c.messages || []).map((m, i) => (
                <div key={i} className={`flex ${m.role === "customer" ? "justify-start" : "justify-end"}`}>
                  <div className={`max-w-[80%] rounded-xl px-3 py-2 text-sm shadow-sm ${m.role === "customer" ? "bg-white" : m.role === "owner" ? "bg-sky-100" : "bg-[#d9fdd3]"}`}>
                    <div className="mb-0.5 text-[11px] font-semibold text-slate-500">
                      {m.role === "customer" ? "Customer" : m.role === "owner" ? "You (owner)" : "Dukaan Dost AI"} · {niceStamp(m.at)}
                    </div>
                    <div className="whitespace-pre-wrap">{m.text}</div>
                    {m.role === "assistant" && m.meta?.intent && (
                      <div className="mt-1 text-[11px] text-slate-500">intent: {m.meta.intent}{m.meta.tools_used?.length ? ` · tools: ${m.meta.tools_used.join(", ")}` : ""}</div>
                    )}
                  </div>
                </div>
              ))}
              {!c.messages?.length && <Empty>No messages.</Empty>}
            </div>
            <form onSubmit={sendReply} className="mt-3 flex gap-2">
              <input
                value={reply}
                onChange={(e) => setReply(e.target.value)}
                maxLength={1000}
                placeholder={c.ai_paused ? "Write your reply…" : "Take over first to reply yourself"}
                disabled={!c.ai_paused}
                className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
              />
              <Button type="submit" disabled={busy || !c.ai_paused || !reply.trim()}>Send</Button>
            </form>
          </>
        )}
      </Card>
    </div>
  );
}
