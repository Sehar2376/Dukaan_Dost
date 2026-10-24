// Inbox: alerts that need the owner + every conversation, with take over / reply / hand back.
import { useEffect, useState } from "react";
import { ArrowLeft, Bell, Check, Hand, MessageCircle, Search, Send, Undo2 } from "../components/icons.jsx";
import { api, clean, niceStamp, useApi } from "../api.js";
import {
  Badge, Button, Card, EmptyState, ErrorNotice, FLAG, LoadingRows, ModelChip, Notice, Tabs, cx, inputCls, useToast,
} from "../components/ui.jsx";

function Alerts({ openChat, refreshFlags }) {
  const toast = useToast();
  const { data, error, loading, reload } = useApi("/flags");
  const [busy, setBusy] = useState(null);

  async function resolve(id) {
    setBusy(id);
    try {
      await api(`/flags/${id}/resolve`, { method: "POST" });
      await reload();
      refreshFlags?.();
      toast("Marked as resolved.");
    } catch (e) {
      toast(e.message, "danger");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card title="Needs your attention" subtitle="Complaints, questions the assistant couldn't answer, high-risk or large orders, and abusive messages.">
      <ErrorNotice error={error} />
      {loading && !data ? <LoadingRows /> : !data?.length ? (
        <EmptyState icon={Check} title="You're all caught up">New alerts appear here as soon as a customer needs you.</EmptyState>
      ) : (
        <ul className="-my-2 divide-y divide-slate-100">
          {data.map((f) => {
            const meta = FLAG[f.type] || { tone: "neutral", label: f.type, icon: Bell };
            const Icon = meta.icon || Bell;
            return (
              <li key={f.id} className="flex flex-wrap items-start gap-4 py-4">
                <span className={cx("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
                  { danger: "bg-red-50 text-red-600", warning: "bg-amber-50 text-amber-700", violet: "bg-violet-50 text-violet-600", brand: "bg-brand-50 text-brand-600", neutral: "bg-slate-100 text-slate-600" }[meta.tone])}>
                  <Icon size={17} aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-slate-900">{meta.label}</p>
                  <p className="mt-0.5 text-sm text-slate-700">{f.reason}</p>
                  <p className="mt-1 text-xs text-slate-500">{f.phone_masked} · {niceStamp(f.created_at)}</p>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" icon={MessageCircle} onClick={() => openChat(f.customer_phone)}>Open chat</Button>
                  <Button size="sm" variant="ghost" icon={Check} onClick={() => resolve(f.id)} loading={busy === f.id}>Resolve</Button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

function Conversations({ phone, setPhone }) {
  const toast = useToast();
  const list = useApi("/conversations");
  const conv = useApi(phone ? `/conversations/${encodeURIComponent(phone)}` : "/", { skip: !phone, ms: 15000 });
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [q, setQ] = useState("");
  const c = phone ? conv.data : null;
  const rows = (list.data || []).filter((x) => !q || `${x.phone_masked} ${x.last_message?.text || ""}`.toLowerCase().includes(q.toLowerCase()));

  async function takeover(paused) {
    setBusy(true);
    try {
      await api(`/conversations/${encodeURIComponent(phone)}/takeover`, { method: "POST", params: { paused } });
      await Promise.all([conv.reload(), list.reload()]);
      toast(paused ? "You're now replying to this customer. The assistant is paused." : "Handed back to the assistant.");
    } catch (e) {
      toast(e.message, "danger");
    } finally {
      setBusy(false);
    }
  }

  async function sendReply(e) {
    e.preventDefault();
    if (!reply.trim()) return;
    setBusy(true);
    try {
      const r = await api(`/conversations/${encodeURIComponent(phone)}/reply`, { method: "POST", body: { text: reply.trim() } });
      setReply("");
      await conv.reload();
      if (!r.sent_to_whatsapp && phone.startsWith("+")) toast("Saved here, but not sent to WhatsApp: WhatsApp isn't connected yet.", "warning");
    } catch (e2) {
      toast(e2.message, "danger");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm lg:grid-cols-[320px_1fr]">
      {/* List */}
      <div className={cx("border-slate-200 lg:border-r", phone && "hidden lg:block")}>
        <div className="border-b border-slate-100 p-3">
          <label className="relative block">
            <span className="sr-only">Search conversations</span>
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" className={cx(inputCls, "pl-9")} />
          </label>
        </div>
        <ErrorNotice error={list.error} className="m-3" />
        {list.loading && !list.data ? <div className="p-3"><LoadingRows /></div> : !rows.length ? (
          <div className="p-4"><EmptyState icon={MessageCircle} title="No conversations">Chats appear here when customers write.</EmptyState></div>
        ) : (
          <ul className="max-h-[64vh] overflow-y-auto scroll-thin">
            {rows.map((x) => (
              <li key={x.phone}>
                <button onClick={() => setPhone(x.phone)}
                  className={cx("w-full border-b border-slate-50 px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-500",
                    phone === x.phone ? "bg-brand-50" : "hover:bg-slate-50")}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold text-slate-900">{x.phone_masked}</span>
                    <span className="text-[11px] text-slate-400">{niceStamp(x.updated_at)}</span>
                  </div>
                  <div className="mt-0.5 flex items-center justify-between gap-2">
                    <span className="truncate text-sm text-slate-500" dir="auto">{x.last_message?.text ? clean(x.last_message.text) : "No messages yet"}</span>
                    {x.ai_paused && <Badge tone="warning">You</Badge>}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Thread */}
      <div className={cx("flex min-w-0 flex-col", !phone && "hidden lg:flex")}>
        {!phone ? (
          <div className="flex flex-1 items-center justify-center p-10"><EmptyState icon={MessageCircle} title="Select a conversation">Pick a customer on the left to read the chat.</EmptyState></div>
        ) : !c ? <div className="p-5"><LoadingRows rows={5} /></div> : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
              <div className="flex items-center gap-2">
                <button onClick={() => setPhone(null)} className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 lg:hidden" aria-label="Back to list"><ArrowLeft size={18} /></button>
                <div>
                  <p className="text-sm font-semibold text-slate-900">{c.phone_masked}</p>
                  <p className="text-xs text-slate-500">{c.ai_paused ? "You are replying" : "Assistant is replying"}</p>
                </div>
              </div>
              {c.ai_paused
                ? <Button size="sm" variant="secondary" icon={Undo2} onClick={() => takeover(false)} loading={busy}>Hand back to assistant</Button>
                : <Button size="sm" icon={Hand} onClick={() => takeover(true)} loading={busy}>Take over</Button>}
            </div>
            {c.ai_paused && <Notice tone="warning" className="mx-4 mt-3">The assistant is paused for this customer. Your replies go straight to them.</Notice>}
            <div className="chat-surface max-h-[52vh] min-h-[320px] flex-1 space-y-3 overflow-y-auto p-4 scroll-thin" role="log" aria-label="Conversation">
              {(c.messages || []).map((m, i) => (
                <div key={i} className={cx("flex", m.role === "customer" ? "justify-start" : "justify-end")}>
                  <div className={cx("max-w-[80%] rounded-2xl px-3.5 py-2.5 text-sm shadow-sm",
                    m.role === "customer" ? "rounded-bl-md bg-white text-slate-800" : m.role === "owner" ? "rounded-br-md bg-amber-50 ring-1 ring-amber-200" : "rounded-br-md bg-brand-600 text-white")}>
                    <p className={cx("mb-0.5 text-[11px] font-semibold", m.role === "assistant" ? "text-brand-100" : "text-slate-500")}>
                      {m.role === "customer" ? "Customer" : m.role === "owner" ? "You" : "Assistant"} · {niceStamp(m.at)}
                    </p>
                    <p className="whitespace-pre-wrap leading-relaxed" dir="auto">{clean(m.text)}</p>
                    {m.role === "assistant" && m.meta?.route?.length ? (
                      <div className="mt-1.5 flex flex-wrap items-center gap-1">{m.meta.route.map((r, j) => <ModelChip key={j} model={r} />)}</div>
                    ) : null}
                  </div>
                </div>
              ))}
              {!c.messages?.length && <EmptyState title="No messages with this customer yet">You can still take over and write to them first.</EmptyState>}
            </div>
            <form onSubmit={sendReply} className="flex gap-2 border-t border-slate-100 p-3">
              <label htmlFor="owner-reply" className="sr-only">Your reply</label>
              <input id="owner-reply" value={reply} onChange={(e) => setReply(e.target.value)} maxLength={1000} dir="auto"
                placeholder={c.ai_paused ? "Write your reply…" : "Take over to reply yourself"} disabled={!c.ai_paused} className={inputCls} />
              <Button type="submit" icon={Send} disabled={busy || !c.ai_paused || !reply.trim()}>Send</Button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}

export default function Inbox({ params, go, refreshFlags }) {
  const flags = useApi("/flags", { ms: 30000 });
  const tab = params.tab || (params.phone ? "chats" : "alerts");
  const phone = params.phone || null;
  const setTab = (t) => go("inbox", { tab: t, phone: t === "chats" ? phone : undefined });
  const setPhone = (p) => go("inbox", { tab: "chats", phone: p || undefined });

  useEffect(() => { if (tab === "alerts") flags.reload(); }, [tab]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-6">
      <Tabs value={tab} onChange={setTab} tabs={[
        { id: "alerts", label: "Needs attention", icon: Bell, count: flags.data?.length },
        { id: "chats", label: "Conversations", icon: MessageCircle },
      ]} />
      {tab === "alerts"
        ? <Alerts openChat={setPhone} refreshFlags={() => { flags.reload(); refreshFlags?.(); }} />
        : <Conversations phone={phone} setPhone={setPhone} />}
    </div>
  );
}
