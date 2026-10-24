// Customer chat simulator: looks like WhatsApp, talks to POST /chat.
import { useEffect, useRef, useState } from "react";
import { api, niceTime, rs } from "../api.js";
import { Badge, Button } from "../components/ui.jsx";

const QUICK = [
  "Assalam o alaikum",
  "Delivery charges kitne hain?",
  "2kg chocolate cake parson shaam 6 baje chahiye",
  "Thora kam kar dein",
  "Haan, confirm",
  "Mera order 2 ghantay late hai!!",
];
const LANG = { roman_urdu: "Roman Urdu", urdu: "Urdu", english: "English", mixed: "Mixed" };

const randomPhone = () => "03" + String(Math.floor(100000000 + Math.random() * 899999999));

function OrderCard({ s, onConfirm, onChange, busy }) {
  return (
    <div className="mt-2 rounded-xl border border-green-200 bg-white p-3 text-sm shadow-sm">
      <div className="mb-2 text-xs font-bold uppercase tracking-wide text-green-700">Order summary</div>
      {s.items.map((it) => (
        <div key={it.product_id} className="flex justify-between gap-3">
          <span>
            {it.quantity} × {it.name}
            {it.discount_percent > 0 && <span className="ml-1 text-xs text-green-700">(-{it.discount_percent}%)</span>}
          </span>
          <span className="font-medium">{rs(it.line_total)}</span>
        </div>
      ))}
      {s.discount > 0 && (
        <div className="flex justify-between text-green-700"><span>Discount</span><span>-{rs(s.discount)}</span></div>
      )}
      <div className="flex justify-between text-slate-600"><span>Delivery</span><span>{rs(s.delivery_fee)}</span></div>
      <div className="mt-1 flex justify-between border-t border-slate-200 pt-1 text-base font-bold">
        <span>Total</span><span>{rs(s.total)}</span>
      </div>
      <div className="mt-2 space-y-0.5 text-xs text-slate-600">
        <div>📍 {s.address}</div>
        <div>🕕 {niceTime(s.delivery_time)}</div>
        <div>💳 {s.payment_type === "cod" ? "Cash on delivery" : s.payment_type}</div>
      </div>
      <div className="mt-3 flex gap-2">
        <Button className="flex-1" onClick={onConfirm} disabled={busy}>Confirm</Button>
        <Button kind="ghost" className="flex-1" onClick={onChange} disabled={busy}>Change</Button>
      </div>
    </div>
  );
}

export default function ChatSim() {
  const [phone, setPhone] = useState("03001234567");
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  // Show earlier messages of this phone number
  useEffect(() => {
    let alive = true;
    api(`/conversations/${encodeURIComponent(phone)}`)
      .then((c) => alive && setMsgs((c.messages || []).map((m) => ({ role: m.role, text: m.text, meta: m.meta || {} }))))
      .catch(() => alive && setMsgs([]));
    return () => {
      alive = false;
    };
  }, [phone]);

useEffect(() => {
  endRef.current?.scrollIntoView({ behavior: "smooth" });
}, [msgs, busy]);
  async function send(message) {
    const m = (message ?? text).trim();
    if (!m || busy) return;
    setText("");
    setError(null);
    setMsgs((x) => [...x, { role: "customer", text: m, meta: {} }]);
    setBusy(true);
    try {
      const r = await api("/chat", { method: "POST", body: { phone, message: m } });
      setMsgs((x) => {
        const out = [...x];
        const last = out[out.length - 1];
        out[out.length - 1] = { ...last, meta: { language: r.language, intent: r.intent, urgent: r.urgent } };
        if (r.ai_paused) out.push({ role: "system", text: "The shop owner has taken over this chat and will reply personally." });
        else out.push({ role: "assistant", text: r.reply, meta: r, summary: r.order_summary });
        return out;
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  // Only the newest card, while nothing has been said after it, can be confirmed or changed
  const lastSummaryIdx = msgs.map((m) => !!m.summary).lastIndexOf(true);

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
      <div className="overflow-hidden rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-3 bg-[#075E54] px-4 py-3 text-white">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white/20">🍰</div>
          <div className="flex-1">
            <div className="font-semibold">Customer chat (simulator)</div>
            <div className="text-xs text-white/80">{busy ? "typing…" : "online"}</div>
          </div>
        </div>
        <div className="chat-bg h-[60vh] min-h-[380px] space-y-2 overflow-y-auto p-4">
          {msgs.length === 0 && (
            <div className="mx-auto mt-10 max-w-sm rounded-xl bg-white/90 p-4 text-center text-sm text-slate-600">
              Type like a customer would, in Roman Urdu, Urdu or English, or tap a quick message on the right.
            </div>
          )}
          {msgs.map((m, i) =>
            m.role === "system" ? (
              <div key={i} className="mx-auto w-fit rounded-lg bg-amber-50 px-3 py-1 text-xs text-amber-800">{m.text}</div>
            ) : (
              <div key={i} className={`flex ${m.role === "customer" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[85%] rounded-xl px-3 py-2 text-sm shadow-sm ${
                    m.role === "customer" ? "bg-[#d9fdd3]" : m.role === "owner" ? "bg-sky-50" : "bg-white"
                  }`}
                >
                  {m.role === "owner" && <div className="mb-0.5 text-xs font-semibold text-sky-700">Shop owner</div>}
                  <div className="whitespace-pre-wrap">{m.text}</div>
                  {m.role === "customer" && m.meta?.intent && (
                    <div className="mt-1 flex flex-wrap justify-end gap-1">
                      <Badge color="blue">{LANG[m.meta.language] || m.meta.language}</Badge>
                      <Badge color={m.meta.intent === "complaint" || m.meta.urgent ? "red" : "slate"}>{m.meta.intent}</Badge>
                    </div>
                  )}
                  {m.summary && (
                    <OrderCard
                      s={m.summary}
                      busy={busy || i !== lastSummaryIdx || i !== msgs.length - 1}
                      onConfirm={() => send("Haan, confirm")}
                      onChange={() => {
                        setText("Ek cheez change karni hai: ");
                        inputRef.current?.focus();
                      }}
                    />
                  )}
                  {m.role === "assistant" && m.meta?.needs_owner && (
                    <div className="mt-1 text-xs text-amber-700">🚨 Owner alerted</div>
                  )}
                </div>
              </div>
            )
          )}
          {busy && <div className="w-fit rounded-xl bg-white px-3 py-2 text-sm text-slate-400 shadow-sm">…</div>}
          <div ref={endRef} />
        </div>
        {error && <div className="bg-red-50 px-4 py-2 text-sm text-red-700">⚠️ {error}</div>}
        <form
          className="flex gap-2 border-t border-slate-200 bg-slate-50 p-3"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <input
            ref={inputRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={1000}
            placeholder="Type a message"
            className="flex-1 rounded-full border border-slate-300 bg-white px-4 py-2 text-sm outline-none focus:border-green-500"
          />
          <Button type="submit" disabled={busy || !text.trim()} className="rounded-full px-5">Send</Button>
        </form>
      </div>

      <div className="space-y-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <label className="text-xs font-medium uppercase tracking-wide text-slate-500">Customer phone</label>
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value.replace(/[^\d+]/g, "").slice(0, 15))}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <p className="mt-1 text-xs text-slate-500">Same number = same customer (memory, past orders).</p>
          <Button kind="ghost" className="mt-2 w-full" onClick={() => setPhone(randomPhone())}>New customer</Button>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Quick messages</div>
          <div className="flex flex-wrap gap-1.5 lg:flex-col">
            {QUICK.map((q) => (
              <button
                key={q}
                onClick={() => send(q)}
                disabled={busy}
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-left text-xs text-slate-700 hover:bg-green-50 disabled:opacity-50"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
        <p className="text-xs leading-relaxed text-slate-500">
          Each message is read by <b>Nemotron Nano</b> (language + intent, shown under your message). Orders and
          bargaining are handled by the <b>Nemotron Super</b> agent; prices and discounts are checked in code.
        </p>
      </div>
    </div>
  );
}
