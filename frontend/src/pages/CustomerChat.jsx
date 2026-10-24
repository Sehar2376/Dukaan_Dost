// Customer chat: the assistant exactly as a customer sees it on WhatsApp, plus what happened behind the scenes.
import { useEffect, useRef, useState } from "react";
import { ArrowRight, Bell, Cpu, Languages, MapPin, Send, Timer, UserPlus, Wrench } from "../components/icons.jsx";
import { INTENT, api, clean, niceTime, rs } from "../api.js";
import { Button, Card, ErrorNotice, Field, ModelChip, cx, inputCls, store } from "../components/ui.jsx";

const PROMPTS = [
  ["Ask a question", "Delivery charges kitne hain?"],
  ["Place an order", "2kg chocolate cake parson shaam 6 baje chahiye"],
  ["Bargain", "Thora kam kar dein"],
  ["Give details", "Ayesha, House 12 Street 5 Block 13-D near Masjid, Gulshan. Cash on delivery"],
  ["Confirm", "Haan, confirm"],
  ["Complain", "Mera order 2 ghantay late hai!!"],
  ["Ask in Urdu", "کیا آپ کے پاس eggless کیک ہے؟"],
];
const LANG = { roman_urdu: "Roman Urdu", urdu: "Urdu", english: "English", mixed: "Mixed" };
const TOOL = {
  get_products: "Checked menu", get_customer: "Looked up customer", check_discount: "Checked discount limit",
  preview_order: "Prepared order summary", confirm_order: "Saved order", create_booking: "Booked a slot", flag_owner: "Alerted owner",
};
const randomPhone = () => "03" + String(Math.floor(100000000 + Math.random() * 899999999));

function Route({ route = [] }) {
  if (!route.length) return null;
  return (
    <span className="inline-flex items-center gap-1">
      {route.map((m, i) => (
        <span key={i} className="inline-flex items-center gap-1">
          {i > 0 && <ArrowRight size={11} className="text-slate-400" aria-hidden />}
          <ModelChip model={m} />
        </span>
      ))}
    </span>
  );
}

function OrderCard({ s, onConfirm, onChange, disabled }) {
  return (
    <div className="mt-2 overflow-hidden rounded-xl border border-slate-200 bg-white text-sm">
      <div className="border-b border-slate-100 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Order summary</div>
      <div className="space-y-1 px-3 py-2.5">
        {s.items.map((it) => (
          <div key={it.product_id} className="flex justify-between gap-3">
            <span className="text-slate-700">{it.quantity} × {it.name}{it.discount_percent > 0 && <span className="ml-1 text-xs text-emerald-700">−{it.discount_percent}%</span>}</span>
            <span className="font-medium text-slate-900">{rs(it.line_total)}</span>
          </div>
        ))}
        {s.discount > 0 && <div className="flex justify-between text-emerald-700"><span>Discount</span><span>−{rs(s.discount)}</span></div>}
        <div className="flex justify-between text-slate-600"><span>Delivery</span><span>{rs(s.delivery_fee)}</span></div>
        <div className="flex justify-between border-t border-slate-100 pt-1.5 text-base font-bold text-slate-900"><span>Total</span><span>{rs(s.total)}</span></div>
        <div className="space-y-0.5 pt-1 text-xs text-slate-500">
          <p className="flex items-start gap-1.5"><MapPin size={12} className="mt-0.5 shrink-0" aria-hidden />{s.address}</p>
          <p>{niceTime(s.delivery_time)} · {s.payment_type === "cod" ? "Cash on delivery" : s.payment_type}</p>
        </div>
      </div>
      <div className="flex gap-2 border-t border-slate-100 p-2">
        <Button size="sm" className="flex-1" onClick={onConfirm} disabled={disabled}>Confirm</Button>
        <Button size="sm" variant="secondary" className="flex-1" onClick={onChange} disabled={disabled}>Change</Button>
      </div>
    </div>
  );
}

function Trace({ last, practice }) {
  const rows = last ? [
    [Languages, "Language", LANG[last.language] || last.language],
    [Cpu, "Intent", INTENT[last.intent] || last.intent],
    [ArrowRight, "Handled by", <Route route={last.route} />],
    [Wrench, "Actions", last.tools_used?.length ? last.tools_used.map((t) => TOOL[t] || t).join(", ") : "None needed"],
    [Bell, "Owner alerted", last.needs_owner ? "Yes" : "No"],
    [Timer, "Reply time", last.ms ? `${(last.ms / 1000).toFixed(1)} s` : "—"],
  ] : [];
  return (
    <Card title="Behind the scenes" subtitle="What happened for the last message">
      {!last ? (
        <p className="text-sm text-slate-500">Send a message to see which model read it, what it understood and what it did.</p>
      ) : (
        <dl className="space-y-2.5 text-sm">
          {rows.map(([Icon, k, v]) => (
            <div key={k} className="flex items-start justify-between gap-3">
              <dt className="flex items-center gap-2 text-slate-500"><Icon size={14} aria-hidden />{k}</dt>
              <dd className="text-right font-medium text-slate-900">{v}</dd>
            </div>
          ))}
        </dl>
      )}
      {practice && (
        <p className="mt-4 rounded-lg bg-slate-50 p-2.5 text-xs text-slate-500">
          Practice mode: replies come from simple rules until an AI key is added on the server.
        </p>
      )}
    </Card>
  );
}

export default function CustomerChat({ health, shop }) {
  const [phone, setPhone] = useState(() => store.get("dd_chat_phone", "03001234567"));
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [last, setLast] = useState(null);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    store.set("dd_chat_phone", phone);
    let alive = true;
    setLast(null);
    api(`/conversations/${encodeURIComponent(phone)}`)
      .then((c) => alive && setMsgs((c.messages || []).map((m) => ({ role: m.role, text: m.text, meta: m.meta || {} }))))
      .catch(() => alive && setMsgs([]));
    return () => { alive = false; };
  }, [phone]);

  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }), [msgs, busy]);

  async function send(message) {
    const m = (message ?? text).trim();
    if (!m || busy) return;
    setText("");
    setError(null);
    setMsgs((x) => [...x, { role: "customer", text: m, meta: {} }]);
    setBusy(true);
    try {
      const r = await api("/chat", { method: "POST", body: { phone, message: m } });
      store.set("dd_chatted", true);
      setLast(r);
      setMsgs((x) => [...x, r.ai_paused
        ? { role: "system", text: "The shop owner has taken over this chat and will reply personally." }
        : { role: "assistant", text: r.reply, meta: r, summary: r.order_summary }]);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  const lastSummaryIdx = msgs.map((m) => !!m.summary).lastIndexOf(true);

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
      {/* Chat window */}
      <div className="flex min-w-0 flex-col self-start overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center gap-3 border-b border-slate-200 bg-brand-900 px-4 py-3 text-white">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white"><img src="/logo-mark.png" alt="" className="h-8 w-8" /></span>
          <div className="min-w-0 flex-1">
            <p className="truncate font-semibold">{shop?.name || "Your shop"}</p>
            <p className="text-xs text-brand-200" aria-live="polite">{busy ? "typing…" : "Replies instantly · Powered by Dukaan Dost"}</p>
          </div>
        </div>

        <div className="chat-surface h-[58vh] min-h-[420px] space-y-3 overflow-y-auto px-4 py-5 scroll-thin" role="log" aria-live="polite" aria-label="Conversation">
          {msgs.length === 0 && (
            <div className="mx-auto mt-12 max-w-sm rounded-2xl bg-white/90 p-5 text-center shadow-sm">
              <p className="text-sm font-semibold text-slate-800">Start a conversation</p>
              <p className="mt-1 text-sm text-slate-500">Write like a customer would, in Urdu, Roman Urdu or English, or pick a message on the right.</p>
            </div>
          )}
          {msgs.map((m, i) => m.role === "system" ? (
            <p key={i} className="mx-auto w-fit rounded-full bg-amber-50 px-3 py-1 text-xs text-amber-800 ring-1 ring-amber-200">{m.text}</p>
          ) : (
            <div key={i} className={cx("flex", m.role === "customer" ? "justify-end" : "justify-start")}>
              <div className={cx("max-w-[82%] rounded-2xl px-3.5 py-2.5 text-sm shadow-sm",
                m.role === "customer" ? "rounded-br-md bg-brand-600 text-white" : m.role === "owner" ? "rounded-bl-md bg-amber-50 ring-1 ring-amber-200" : "rounded-bl-md bg-white text-slate-800")}>
                {m.role === "owner" && <p className="mb-0.5 text-xs font-semibold text-amber-800">Shop owner</p>}
                <p className="whitespace-pre-wrap leading-relaxed" dir="auto">{clean(m.text)}</p>
                {m.summary && (
                  <OrderCard s={m.summary} disabled={busy || i !== lastSummaryIdx || i !== msgs.length - 1}
                    onConfirm={() => send("Haan, confirm")}
                    onChange={() => { setText("Ek cheez change karni hai: "); inputRef.current?.focus(); }} />
                )}
                {m.role === "assistant" && (m.meta?.route?.length || m.meta?.intent) ? (
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500">
                    <Route route={m.meta.route} />
                    {m.meta.intent && <span>· {INTENT[m.meta.intent] || m.meta.intent}</span>}
                    {m.meta.needs_owner && <span className="font-medium text-amber-700">· Owner alerted</span>}
                  </div>
                ) : null}
              </div>
            </div>
          ))}
          {busy && (
            <div className="flex w-fit gap-1 rounded-2xl rounded-bl-md bg-white px-4 py-3 shadow-sm" aria-label="Assistant is typing">
              <span className="typing-dot h-1.5 w-1.5 rounded-full bg-slate-400" /><span className="typing-dot h-1.5 w-1.5 rounded-full bg-slate-400" /><span className="typing-dot h-1.5 w-1.5 rounded-full bg-slate-400" />
            </div>
          )}
          <div ref={endRef} />
        </div>

        {error && <ErrorNotice error={error} className="m-3" />}
        <form className="flex items-center gap-2 border-t border-slate-200 bg-white p-3" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <label htmlFor="chat-input" className="sr-only">Message</label>
          <input id="chat-input" ref={inputRef} value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} dir="auto"
            placeholder="Type a message" autoComplete="off" className={cx(inputCls, "h-11 rounded-full px-4")} />
          <Button type="submit" size="icon" className="h-11 w-11 shrink-0 rounded-full" disabled={busy || !text.trim()} aria-label="Send">
            <Send size={18} aria-hidden />
          </Button>
        </form>
      </div>

      {/* Side panel */}
      <div className="space-y-6">
        <Card title="Try these messages" subtitle="A full order takes about one minute">
          <ul className="space-y-2">
            {PROMPTS.map(([label, msg]) => (
              <li key={msg}>
                <button onClick={() => send(msg)} disabled={busy}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-left transition-colors hover:border-brand-300 hover:bg-brand-50 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">
                  <span className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">{label}</span>
                  <span className="block text-sm text-slate-800" dir="auto">{msg}</span>
                </button>
              </li>
            ))}
          </ul>
        </Card>
        <Trace last={last} practice={health?.mock_ai} />
        <Card title="Customer" subtitle="Same number = same customer, with memory of past orders">
          <Field label="Phone number">
            <input value={phone} onChange={(e) => setPhone(e.target.value.replace(/[^\d+]/g, "").slice(0, 15))} className={inputCls} inputMode="tel" />
          </Field>
          <Button variant="secondary" size="sm" icon={UserPlus} className="mt-3" onClick={() => setPhone(randomPhone())}>New customer</Button>
        </Card>
      </div>
    </div>
  );
}
