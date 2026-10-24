# Dukaan Dost: frontend

The owner's dashboard and a customer chat simulator, built with React 18, Vite 6, Tailwind CSS 4,
Recharts and Lucide icon shapes (bundled locally in `src/components/icons.jsx`, nothing extra to download). It only talks to the backend API and never sees any API key.

| Page | What the owner does there |
|---|---|
| **Overview** | Two-minute getting-started steps, today's numbers, alerts, recent orders, how the AI routing works |
| **Customer chat** | Chat exactly as a customer would on WhatsApp; see which model handled each message and what it did |
| **Inbox** | Alerts that need the owner, and every conversation (take over, reply, hand back) |
| **Orders** | Orders with the cash-on-delivery risk check and reasons; change status; bookings tab |
| **Customers** | Returning customers with order history and trust level |
| **Insights** | Sales (day/month, chart, best sellers, end-of-day report), Nemotron Ultra business advice, Tavily market prices |
| **Settings** | Shop setup (paste your menu, Nemotron Super reads it), AI status, usage, cost and routing savings |

Pages have their own links (for example `#/orders?tab=bookings`), so a refresh keeps you on the same page.

## Run it on your laptop

Needs **Node.js 18 or newer** and the backend running on port 8000.

```bash
cd frontend
npm install
copy .env.example .env      # Mac/Linux: cp .env.example .env
npm run dev
```

Open http://localhost:5173. Chrome shows "Not secure" for `http://localhost`; that is normal on a laptop and
disappears on the deployed site, which uses HTTPS.

## Settings

| Setting | Where | Value |
|---|---|---|
| `VITE_API_URL` | `frontend/.env` (laptop) or Vercel → Environment Variables | `http://localhost:8000` or your Render link |
| Footer email, phone, city, GitHub link | `src/site.js` | Edit the values; leave `phone` empty to hide it |

## Deploy on Vercel

1. vercel.com → **Add New → Project** → import the GitHub repo.
2. **Root Directory**: `frontend` · Framework: **Vite**.
3. **Environment Variables**: `VITE_API_URL` = your Render backend link.
4. **Deploy**. The Vercel link is your demo URL.

## Files

| File | What it is |
|---|---|
| `index.html` | Page title, description, favicon and font |
| `public/` | Logo (`logo-mark.png`, `logo-full.png`) and browser icons (`favicon.png`, `favicon.ico`, `apple-touch-icon.png`) |
| `src/main.jsx` | Starts the app |
| `src/App.jsx` | Page routing, connection notice, layout |
| `src/site.js` | Footer details (email, phone, city, links) |
| `src/api.js` | Calls the backend, refreshes data, formats rupees and times |
| `src/index.css` | Brand colours (from the logo), font, chat background |
| `src/components/ui.jsx` | Cards, buttons, badges, tabs, tables, empty and loading states, toasts |
| `src/components/Layout.jsx` | Logo, sidebar, phone menu, page header, footer |
| `src/components/icons.jsx` | The icons the app uses, as inline SVG (Lucide shapes, ISC License) |
| `src/pages/Overview.jsx` | Overview page |
| `src/pages/CustomerChat.jsx` | Customer chat simulator (`POST /chat`) |
| `src/pages/Inbox.jsx` | Alerts and conversations |
| `src/pages/Orders.jsx` | Orders and bookings |
| `src/pages/Customers.jsx` | Customers |
| `src/pages/Insights.jsx` | Sales, business advice, market prices |
| `src/pages/Settings.jsx` | Shop setup, AI and usage |

## Accessibility

Keyboard navigation with visible focus rings, a "Skip to content" link, labelled form fields and buttons,
live regions for new chat messages, right-to-left text for Urdu (`dir="auto"`), colour contrast that meets
WCAG AA for body text, and reduced motion when the device asks for it.
