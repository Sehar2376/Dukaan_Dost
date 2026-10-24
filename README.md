# Dukaan Dost 🛍️

**An AI WhatsApp assistant for small Pakistani businesses — powered by NVIDIA Nemotron on Nebius Token Factory.**

> Nebius x NVIDIA Global AI Hackathon · Track: **Best Apps and Agents** · License: MIT

Demo: _coming soon_ · Video: _coming soon_

## The problem
Millions of small Pakistani businesses (home bakers, boutiques, tailors, pharmacies) run entirely on WhatsApp.
Owners answer the same questions all day, miss orders when busy, lose money on fake cash-on-delivery (COD) orders,
and have no clear view of daily sales or profit.

## What Dukaan Dost does
- Talks to customers in **Urdu, Roman Urdu or English** (and mixed) and replies in the same style
- Answers FAQs, takes **orders and bookings**, **bargains within the owner's limits**
- **Flags risky COD orders** with reasons before they ship
- Remembers repeat customers, routes complaints and big orders to the owner
- Gives the owner **daily and monthly sales and profit** summaries
- **AI business advisor**: Nemotron 3 Ultra turns the month's numbers into 3-5 practical tips
- **Market price check** (Tavily): "What do other shops charge for this?" — web search + Nemotron Super + Python comparison
- **Nightly owner report**: a background job adds up the day and WhatsApps the owner (runs as a Nebius Serverless Job)

## How we use NVIDIA Nemotron + Nebius Token Factory
| Model (via Token Factory) | Used for | Why |
|---|---|---|
| Nemotron 3 Nano | Language + intent + urgency detection, FAQ replies, summaries | Fast and cheap for every message |
| Nemotron 3 Super | Tool-calling agent for orders, bookings, bargaining; reading the owner's menu; reading prices out of Tavily search results | Stronger reasoning for multi-step tasks |
| Nemotron 3 Ultra | Monthly AI business advisor (`GET /advice/monthly`), only when the owner asks; answer cached | Deep reasoning over the month's numbers; rare call, so cost stays tiny (~1 cent) |

Every customer message goes through the Token Factory API (OpenAI-compatible). Prices, discounts, totals and
COD risk scores are always calculated **in code**, never by the model, so a customer can't trick the AI
into a bigger discount.

## Architecture
```
Customer (WhatsApp via Twilio / web chat) -> FastAPI
  -> Nemotron Nano: language, intent, urgent
       -> FAQ: answer from shop data
       -> order / booking / bargain: Nemotron Super agent + tools
  -> COD risk rules (Python) -> Firestore -> Owner dashboard (React)

Owner: "What do others charge?" -> Tavily web search -> Nemotron Super reads prices -> Python compares
Every night: daily_report.py (Nebius Serverless Job) -> Nano note -> owner's WhatsApp
Monthly: numbers (Python) + market prices -> Nemotron Ultra -> 3-5 tips
```

## Run it locally
```bash
git clone https://github.com/Sehar2376/Dukaan_Dost.git
cd Dukaan_Dost/backend
python -m venv venv
venv\Scripts\activate          # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy ..\.env.example .env      # Mac/Linux: cp ../.env.example .env   -> then add your NEBIUS_API_KEY
uvicorn main:app --reload
```
Open http://localhost:8000/docs and try `POST /chat` with
`{"phone": "03001234567", "message": "Delivery charges kitne hain?"}`.

No API key yet? Leave `NEBIUS_API_KEY` empty: the app runs in **practice mode** ($0). A rule-based practice agent
(`practice.py`) uses the same tools as the real agent, so orders, bargaining limits, COD risk and alerts can all be tested.

Load demo data (a bakery, 20 customers, ~3 months of orders, all labelled demo) into the running server:
`POST /admin/load-demo` from the `/docs` page (works with or without Firebase).

**Frontend** (second terminal, needs Node.js 18+):
```bash
cd frontend
npm install
copy .env.example .env         # Mac/Linux: cp .env.example .env
npm run dev
```
Open http://localhost:5173: the owner dashboard (Overview, Customer chat, Inbox, Orders, Customers, Insights,
Settings). Start with the two-minute steps on the Overview page. Details in [frontend/README.md](frontend/README.md).

Tests: `pytest -q` (59 offline tests, no key needed) · Classifier accuracy: `python test_classify.py` (needs key)

## API endpoints
Interactive docs for every endpoint: `/docs` on the running server.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/chat` | Customer message in, AI reply out (web chat simulator) |
| POST | `/webhook/whatsapp` | Twilio WhatsApp messages (signature checked) |
| GET | `/orders` · PATCH `/orders/{id}` | Orders with COD risk level and reasons · mark delivered / cancelled |
| GET | `/flags` · POST `/flags/{id}/resolve` | Owner alerts: complaints, unknown questions, high-risk / large orders, abuse |
| GET | `/conversations` · `/conversations/{phone}` | Chats for the owner |
| POST | `/conversations/{phone}/takeover` · `/reply` | Owner pauses the AI and replies |
| GET | `/bookings` · `/customers` | Bookings, customer memory |
| GET/POST | `/setup` · `/setup/parse` · `/setup/save` | 5-minute owner setup (Super reads a pasted menu) |
| GET | `/summary/daily` · `/summary/monthly` | Sales, profit, top products, chart data, AI note (Nano) |
| GET | `/advice/monthly` | AI business advisor (Nemotron 3 Ultra), cached |
| GET | `/usage` | Today's AI calls, tokens and estimated cost |
| POST | `/market/check` · GET `/market/checks` | Market price check: Tavily search → Nemotron Super → Python comparison (saved 24 h) |
| POST | `/admin/run-daily-report` · GET `/reports` | Nightly owner report (same code as the Serverless Job) |
| POST | `/admin/load-demo` | Fill the database with labelled demo data (bakery, customers, orders) |

## Deploy
The repo includes `render.yaml`: on Render choose **New + → Blueprint**, pick this repo, and fill in the secret
values it asks for (`NEBIUS_API_KEY`, Twilio). Add the Firebase key as a Secret File named `firebase-key.json`.
The frontend deploys on Vercel: import the repo, set **Root Directory** to `frontend`, and add `VITE_API_URL` = your Render URL.

## Bonus: Tavily, Nebius Serverless, WhatsApp, Firebase
All optional. Each one switches on when its setting is filled in `backend/.env`; empty = the app still works.

| Feature | Setting | Without it |
|---|---|---|
| Real Nemotron AI | `NEBIUS_API_KEY` | Practice mode (fake AI, $0) |
| Market price check | `TAVILY_API_KEY` (free at app.tavily.com) | Clearly labelled sample results |
| Saved data | `FIREBASE_CREDENTIALS=firebase-key.json` | In-memory data (lost when the server stops) |
| WhatsApp | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `PUBLIC_BASE_URL` | Web chat simulator only |
| Nightly report on WhatsApp | `OWNER_WHATSAPP` (+ Twilio) | Report saved in the dashboard only |

**Nebius Serverless (optional, needs a Nebius AI Cloud account).** The `Dockerfile` packages the backend.
- *Serverless Job* (nightly report, a minute of CPU per run):
  `nebius ai job create --name dukaan-report --image <dockerhub-user>/dukaan-dost:1 --container-command python --args "daily_report.py" --env "FIREBASE_CREDENTIALS=firebase-key.json" --inject-file "firebase-key.json:/app/backend/firebase-key.json" --env-secret NEBIUS_API_KEY=<secret> --platform cpu-d3 --preset 4vcpu-16gb`
- *Serverless Endpoint* (the API itself, instead of Render):
  `nebius ai endpoint create --name dukaan-api --image <dockerhub-user>/dukaan-dost:1 --container-port 8000 --platform cpu-d3 --preset 4vcpu-16gb`
  Endpoints bill per second while running: delete it when you don't need it (`nebius ai endpoint delete`).
Secrets are passed as environment variables / secrets at create time, never baked into the image.

## Feedback on Nebius and NVIDIA
See [FEEDBACK.md](FEEDBACK.md).

## Project structure
```
backend/
  main.py        FastAPI app and all endpoints
  ai.py          Token Factory / Nemotron Nano + Super + Ultra calls, cost tracking
  agent.py       Nemotron Super tool-calling loop (max 6 steps)
  tools.py       get_products, check_discount, preview/confirm_order, create_booking, flag_owner
  risk.py        COD risk rules (pure Python)
  summary.py     daily/monthly numbers + insights for Ultra advice (all maths in Python)
  practice.py    practice-mode agent (no key): simple rules + the same tools, replies start with (practice)
  market.py      Tavily market price check (search -> Super reads prices -> Python compares)
  daily_report.py  nightly owner report (background job / Nebius Serverless Job)
  db.py          Firestore (or in-memory when FIREBASE_CREDENTIALS is empty)
  prompts/       system prompts as .txt files
  tests/         offline tests with a fake Nemotron (pytest -q)
frontend/
  src/pages/     Overview, CustomerChat, Inbox, Orders, Customers, Insights, Settings
  src/components ui.jsx (design system), Layout.jsx (logo, sidebar, footer)
  src/site.js    footer contact details
Dockerfile       container for Nebius Serverless Endpoints / Jobs (optional)
sample_data/     demo shop + load_sample.py (20 customers, ~3 months of demo orders)
```

## Built during the hackathon
All code was written during the submission period (started Sep 25, 2026).

## License
MIT — see [LICENSE](LICENSE).
