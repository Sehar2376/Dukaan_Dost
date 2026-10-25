import { useCallback, useEffect, useState } from "react";
import { API_URL, useApi } from "./api.js";
import { Footer, PageHeader, PAGES, Sidebar } from "./components/Layout.jsx";
import { Notice, ToastProvider } from "./components/ui.jsx";
import Overview from "./pages/Overview.jsx";
import CustomerChat from "./pages/CustomerChat.jsx";
import Inbox from "./pages/Inbox.jsx";
import Orders from "./pages/Orders.jsx";
import Customers from "./pages/Customers.jsx";
import Insights from "./pages/Insights.jsx";
import Settings from "./pages/Settings.jsx";

const VIEWS = { overview: Overview, chat: CustomerChat, inbox: Inbox, orders: Orders, customers: Customers, insights: Insights, settings: Settings };

// Simple hash routing: #/orders?tab=bookings  (links can be shared and survive a refresh)
function readHash() {
  const [path, query = ""] = window.location.hash.replace(/^#\/?/, "").split("?");
  const page = VIEWS[path] ? path : "overview";
  return { page, params: Object.fromEntries(new URLSearchParams(query)) };
}

export default function App() {
  const [route, setRoute] = useState(readHash);
  const health = useApi("/", { ms: 60000 });
  const setup = useApi("/setup", { ms: 120000 });
  const flags = useApi("/flags", { ms: 120000 });

  useEffect(() => {
    const onHash = () => { setRoute(readHash()); window.scrollTo(0, 0); };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const go = useCallback((page, params = {}) => {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null)).toString();
    window.location.hash = `/${page}${q ? `?${q}` : ""}`;
  }, []);

  const meta = PAGES.find((p) => p.id === route.page);
  const View = VIEWS[route.page];
  const shop = setup.data?.shop;

  useEffect(() => {
    document.title = `${meta.label} · Dukaan Dost`;
  }, [meta.label]);

  return (
    <ToastProvider>
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:shadow">
        Skip to content
      </a>
      <div className="min-h-screen lg:flex">
        <Sidebar page={route.page} go={go} alerts={flags.data?.length || 0} shop={shop} />
        <div className="flex min-w-0 flex-1 flex-col">
          <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
            {health.error && (
              <Notice tone="warning" title="Can't reach the Dukaan Dost server" className="mb-6">
                The dashboard will update as soon as the connection is back.
                <details className="mt-1 text-xs">
                  <summary className="cursor-pointer">Technical details</summary>
                  Server address: <code>{API_URL}</code>. On a laptop, start the backend with <code>uvicorn main:app --reload</code>;
                  online, check <code>VITE_API_URL</code>.
                </details>
              </Notice>
            )}
            <PageHeader title={meta.label} desc={meta.desc} />
            <div className="mt-6">
              <View go={go} params={route.params} health={health.data} shop={shop} refreshFlags={flags.reload} />
            </div>
          </main>
          <Footer go={go} />
        </div>
      </div>
    </ToastProvider>
  );
}
