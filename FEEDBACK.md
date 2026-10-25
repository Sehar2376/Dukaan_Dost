# Feedback: Nebius Token Factory and NVIDIA Nemotron

From the Dukaan Dost team (Karachi, Pakistan, with one teammate in Italy), written during the Nebius x NVIDIA Global AI Hackathon, October 2026.

We built a Roman Urdu shop assistant for small businesses, using Nemotron 3 Nano, Super and Ultra through Token Factory. Below is what helped us most and a few suggestions that we think would make the platform easier for teams like ours, especially first-time builders and teams outside the supported billing countries.

## What worked well

- **OpenAI-compatible API.** We used the standard `openai` Python SDK and only changed `base_url`. Moving between Nano, Super and Ultra is just a different model name, so one code path serves all three models. This saved us a lot of time.
- **Three model sizes make cost control practical.** Nano handles every incoming message, Super runs the tool-calling order agent, and Ultra is reserved for one rare, heavy job (monthly business advice). Being able to pick the right size per task is what makes an AI assistant affordable for a small shop.
- **Thinking on/off per call.** `chat_template_kwargs.enable_thinking` let us keep fast calls fast and turn reasoning on only for Ultra's advice.
- **Exact model IDs in the playground.** The model ID shown on each model's page (and in its link) meant we never had to guess names.
- **Tool calling on Nemotron 3 Super.** Super worked well as the agent for orders, bookings and bargaining, with our own tools and a 6-step limit.
- **Helpful support.** When we asked about billing from Pakistan, the support team replied clearly and quickly, which helped us plan a workaround early.

## Suggestions

1. **Billing for more countries.** Our team is in Pakistan, which isn't currently supported for billing, so a teammate in Italy created the account and shared access. Supporting more countries or local payment options would open Token Factory to many builders across South Asia. For hackathons, a credit-only participant account (no payment method needed) would also solve this.
2. **Clearer credit display.** Our account showed the trial bonus and the promo credit as separate amounts, which at first made us think we had less credit than we did. One combined "available credit" figure, with a breakdown, would remove the confusion.
3. **Promo code limits.** A second promo code was refused with "Promocode apply limit exceeded". A short note on how many codes one account can use would help.
4. **Model catalog guidance.** Searching "Nemotron" lists many variants (Nemotron 3 Nano, Super, Ultra, Nano V2, Super VL, Nano-Omni, Llama-3.1-Nemotron and others). A short "which one should I use?" line per model, or a recommended starter set, would help new users choose quickly.
5. **Regions in one place.** Nemotron 3 Ultra was served from a different regional address than the other models. We added an automatic fallback in code (main address, then the regional address, then Super). A region table next to each model, or one address for all models, would make this simpler.
6. **Structured output.** We had to clean up and parse JSON from model replies. A documented JSON or structured-output mode for Nemotron models on Token Factory would make agent apps more reliable.
7. **Serverless for small teams.** Token Factory and Nebius AI Cloud (Serverless Endpoints and Jobs) felt like separate products with separate accounts. A small free allowance for hackathon participants, plus a short "deploy a FastAPI app" example using the same credit, would let more teams try Serverless. We deployed on a free host this time and kept a `Dockerfile` ready for Serverless.
8. **Usage per API key.** Seeing tokens and cost per key in the dashboard would help teams that share one account. We built our own usage tracker for this (`GET /usage`).

## NVIDIA Nemotron

- **Nemotron 3 Nano** is fast and cheap enough to run on every customer message, including mixed Roman Urdu, Urdu and English.
- **Nemotron 3 Super** handled multi-step tool calling for orders and bargaining well, as long as all prices and limits were checked in our code.
- **Nemotron 3 Ultra** gives detailed, practical monthly advice from the shop's numbers. Because we call it rarely and cache the result, its cost stays small.
- **Suggestion:** more examples for South Asian languages (Roman Urdu, Urdu script and code-mixing) in the docs would help builders in the region trust the models for local use.

**Our quick test:** out of 10 customer messages (Roman Urdu, Urdu and English), Nemotron 3 Nano got the language right 9 times and the intent right 8 times.

Thank you to the Nebius and NVIDIA teams for the credits, the support and the chance to build this.
