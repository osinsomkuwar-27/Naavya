# WhatsApp Business Sandbox Setup — Naavya

Owner: Soham
Priority: **Day 1** (per team responsibility table — the whole pipeline
demo depends on this being live early, and the fallback trigger is
"if sandbox isn't approved by Day 2, switch to web mic recorder").

## What you need

1. A Meta Developer account: https://developers.facebook.com
2. A test WhatsApp Business app created in the Meta App Dashboard
3. A test phone number (Meta provides one free per app for the sandbox —
   no need for your own business-verified number for the hackathon)

## Setup steps

1. Go to Meta App Dashboard → create a new app → select **Business**
   type → add the **WhatsApp** product.
2. Under WhatsApp → API Setup, note down:
   - `Temporary access token` → set as `WHATSAPP_ACCESS_TOKEN` in `.env`
   - `Phone number ID` → set as `WHATSAPP_PHONE_NUMBER_ID` in `.env`
   - The test recipient number Meta gives you for sending test messages
3. Set a webhook verify token of your choosing (any random string) →
   set as `WHATSAPP_VERIFY_TOKEN` in `.env`. This must match exactly
   what you enter in the Meta dashboard webhook config.
4. Expose your local FastAPI server publicly so Meta can reach it
   (Meta will not call `localhost`):
   ```bash
   ngrok http 8000
   ```
   Use the `https://xxxx.ngrok.io` URL it gives you.
5. In Meta Dashboard → WhatsApp → Configuration → Webhook:
   - Callback URL: `https://xxxx.ngrok.io/webhook/whatsapp`
   - Verify token: same string as `WHATSAPP_VERIFY_TOKEN`
   - Subscribe to the `messages` field
6. Meta will call your `GET /webhook/whatsapp` endpoint once to verify
   — `webhook.py`'s `verify_webhook()` handles this automatically as
   long as your `.env` token matches.
7. Send a test WhatsApp voice note from your phone to the sandbox test
   number → it should hit `POST /webhook/whatsapp` and show up in your
   server logs.

## Known sandbox limitations (flag these to the team)

- The temporary access token expires after ~24 hours — regenerate it
  each day of the hackathon, or generate a longer-lived token via a
  System User if this becomes a blocker.
- The sandbox can only message phone numbers you've explicitly added
  as test recipients in the dashboard (max 5 on the free tier) — fine
  for a demo, not for a real pilot.
- Voice notes arrive as `.ogg` (Opus codec) — `asr/transcribe.py`
  already handles this via a temp file, no conversion needed for
  Whisper.

## Fallback trigger (per Open Decisions table)

If the sandbox isn't approved/working by **Day 2**, Soham + Osin agreed
the primary demo path switches to the web mic recorder input
(`backend/api/routes/assess.py` already accepts both input types — see
that file's `InputSource` handling — so no pipeline logic changes,
just which entry point gets demoed live).

## Required env vars (add to `.env.example`)

```
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
```