// Talks to the Dukaan Dost backend (FastAPI). Set VITE_API_URL in .env (see .env.example).
import { useCallback, useEffect, useRef, useState } from "react";

export const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

export async function api(path, { method = "GET", body, params } = {}) {
  const url = new URL(API_URL + path);
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  });
  let res;
  try {
    res = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
      throw new Error("The server is waking up or busy. Please try again in a few seconds.");
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    const d = data && data.detail;
    throw new Error(typeof d === "string" ? d : d ? JSON.stringify(d) : `Error ${res.status}`);
  }
  return data;
}

// Load data and refresh it every `ms` (30 s by default: keeps Firestore reads low).
export function useApi(path, { params, ms = 30000, skip = false } = {}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(!skip);
  const key = path + JSON.stringify(params || {});
  const keyRef = useRef(key);
  keyRef.current = key;

  const reload = useCallback(async () => {
    if (skip) return;
    const myKey = key;
    try {
      const d = await api(path, { params });
      if (keyRef.current === myKey) {
        setData(d);
        setError(null);
      }
    } catch (e) {
      if (keyRef.current === myKey) setError(e.message);
    } finally {
      if (keyRef.current === myKey) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, skip]);

  useEffect(() => {
    setLoading(!skip);
    reload();
    if (!ms || skip) return undefined;
    const t = setInterval(reload, ms);
    return () => clearInterval(t);
  }, [reload, ms, skip]);

  return { data, error, loading, reload };
}

// Practice-mode replies start with "(mock)" or "(practice)"; the badges already say that, so hide the prefix.
export const clean = (s) => String(s ?? "").replace(/^\((mock agent|mock|practice)\)\s*/i, "");

export const INTENT = {
  faq: "Question", order: "Order", bargain: "Bargaining", booking: "Booking", complaint: "Complaint",
  greeting: "Greeting", abuse: "Abuse", other: "Other",
};

export const rs = (n) => "Rs " + Math.round(Number(n) || 0).toLocaleString("en-US");

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// "2026-10-22 18:00" -> "Thu 22 Oct, 6:00 pm"
export function niceTime(s) {
  if (!s) return "";
  const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
  if (!m) return s;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  let h = Number(m[4]);
  const ap = h >= 12 ? "pm" : "am";
  h = h % 12 || 12;
  return `${DAYS[d.getDay()]} ${Number(m[3])} ${MONTHS[d.getMonth()]}, ${h}:${m[5]} ${ap}`;
}

// ISO time saved by the backend (UTC) -> "21 Oct, 3:05 pm" in the viewer's local time
export function niceStamp(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  let h = d.getHours();
  const ap = h >= 12 ? "pm" : "am";
  h = h % 12 || 12;
  return `${d.getDate()} ${MONTHS[d.getMonth()]}, ${h}:${String(d.getMinutes()).padStart(2, "0")} ${ap}`;
}

export const todayISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
export const thisMonth = () => todayISO().slice(0, 7);
