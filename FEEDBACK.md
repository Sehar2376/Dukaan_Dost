# Feedback: Nebius Token Factory, Nebius AI Cloud and NVIDIA Nemotron

Written by the Dukaan Dost team (Karachi, Pakistan + Italy) during the Nebius x NVIDIA Global AI Hackathon.
<!-- TEAM: edit this file with your own experience after testing with the real key. Keep it honest. -->

## What worked well
- **OpenAI-compatible API.** We used the standard `openai` Python SDK with a different `base_url`. Switching
  between Nemotron 3 Nano, Super and Ultra is just a different model name, so one code path serves all three.
- **Three model sizes = real cost control.** Nano handles every message cheaply, Super does tool calling for
  orders, and Ultra is kept for one rare, heavy job (monthly business advice). This is how we plan to make our $61 credit cover
  development, testing and the judging period.
- **Thinking switch.** `chat_template_kwargs.enable_thinking` let us turn reasoning off for fast calls and on
  for Ultra advice.
- **Playground "View code".** Copying exact model IDs from the playground avoided guessing names.
- **Roman Urdu.** <!-- TEAM: add your accuracy result from `python test_classify.py`, e.g. "Language 14/15, intent 13/15" -->

## What was hard / suggestions
- **Billing from Pakistan.** Our team in Pakistan could not add a payment method, so a teammate in Italy had to
  own the account and share access. Supporting more countries (or local payment methods) would open Token
  Factory to many more builders in South Asia.
- **Promo codes.** A second promo code was refused with "Promocode apply limit exceeded". A clearer message
  about how many codes one account can use would help.
- **Model regions.** Nemotron 3 Ultra was listed under the us-central1 address. We added an automatic fallback
  (main address → us-central1 → Super). A single address for all models, or a clear region table next to each
  model, would make this simpler.
- **Serverless from the same account.** Token Factory credit and Nebius AI Cloud (Serverless Endpoints / Jobs)
  felt like separate products. One account, one credit balance and a short "deploy a FastAPI app" example would
  make it easier for small teams to try Serverless.
- **Usage per key.** Seeing tokens and cost per API key in the dashboard would help teams who share one account.

## NVIDIA Nemotron
- <!-- TEAM: one or two sentences each on Nano, Super (tool calling) and Ultra after real testing. -->
