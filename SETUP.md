# Superorder Deck Generator — Slack Agent Setup

## What this does

You DM the Slack bot → it scans Pipefy for chains in **00OM | Log HQ Info/Send Instructions** →
shows you a list → you pick one → it asks Maanav or Sephra → generates the `.pptx` → uploads to Slack.

```
You: generate deck
Bot: Scanning Pipefy...
     Chains in 00OM — pick a number:
     1. Hidden Grounds (Corporate) — PoC: Anand Patel
     2. Thai Chili 2Go — PoC: Mike Chen
     3. Qdoba Southwest — PoC: Sara Lee

You: 2
Bot: ✅ Got it — Thai Chili 2Go
     Who is the Account Manager?
     1. Maanav Patel
     2. Sephra Engel

You: 1
Bot: ⚙️ Generating deck...
     ✅ [uploads ThaiChili2Go_Integration_Call_Deck.pptx]
```

---

## Step 1 — Get your Pipefy Phase ID

Run this once to find the phase ID for 00OM:

```bash
export PIPEFY_TOKEN="your_token_here"
python pipefy_query.py --get-phases
```

Look for the line: `[XXXXXXXXX] 00OM | Log HQ Info/Send Instructions`
Copy that number — that's your `PIPEFY_PHASE_ID`.

---

## Step 2 — Create the Slack App

1. Go to **https://api.slack.com/apps** → **Create New App** → **From scratch**
2. Name it: `Deck Generator` (or anything)
3. Pick your Superorder workspace

### OAuth Scopes (Bot Token Scopes)
Under **OAuth & Permissions → Scopes → Bot Token Scopes**, add:
- `chat:write` — post messages
- `im:history` — read DM messages
- `im:read` — access DM channels
- `files:write` — upload the generated PPTX
- `app_mentions:read` — optional, for @mentions in channels

4. Click **Install to Workspace** → copy the **Bot User OAuth Token** (`xoxb-...`)
5. Under **Basic Information**, copy the **Signing Secret**

---

## Step 3 — Deploy the server

### Option A: Railway (easiest, free tier available)

```bash
# Install Railway CLI
npm i -g @railway/cli
railway login

# From the deck-agent/ folder:
railway init
railway up

# Set environment variables:
railway variables set SLACK_BOT_TOKEN=xoxb-...
railway variables set SLACK_SIGNING_SECRET=...
railway variables set PIPEFY_TOKEN=...
railway variables set PIPEFY_PHASE_ID=XXXXXXXXX
```

Railway gives you a URL like `https://deck-agent-production.up.railway.app`

### Option B: Render (also free tier)

1. Push the `deck-agent/` folder to a GitHub repo
2. Go to render.com → **New Web Service** → connect repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn slack_agent:app --bind 0.0.0.0:$PORT`
5. Add the same 4 env vars under **Environment**

---

## Step 4 — Connect Slack to your server

Back in your Slack App settings:

### Enable Event Subscriptions
1. Go to **Event Subscriptions** → toggle **Enable Events**
2. Request URL: `https://YOUR-SERVER-URL/slack/events`
3. Slack will send a challenge — your server must respond (it does automatically)
4. Under **Subscribe to bot events**, add: `message.im`
5. Save changes

### Enable Direct Messages
1. Go to **App Home** → toggle **Allow users to send Slash commands and messages from the messages tab**

---

## Step 5 — Add the template file

Place `Superorder_Integration_Call_Deck.pptx` in the same folder as `generate_deck.py` on your server.

On Railway/Render, you can either:
- Commit it to your repo (fine since it's internal)
- Or upload it and set `TEMPLATE_PATH` env var to point to it

---

## Step 6 — Test it

1. In Slack, find your bot under **Apps** in the sidebar
2. Send it a DM: `generate deck`
3. Watch the magic happen 🎉

---

## Customization

**Add more AM options** — edit `handle_message()` in `slack_agent.py`:
```python
elif text_clean in ["3", "david"]:
    am = "David"
    agenda_variant = "maanav"  # use same slide variant
```

**Change which products appear** — edit `build_deck()` in `generate_deck.py`

**Sessions reset automatically** after each deck is generated (or on server restart).
For persistence across restarts, swap `SESSIONS = {}` with Redis.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Bot doesn't respond | Check Event Subscriptions URL is correct and server is running |
| Pipefy returns empty list | Verify `PIPEFY_PHASE_ID` — run `--get-phases` to double-check |
| PPTX looks wrong | Open the template, confirm placeholder text matches `build_replacements()` in `generate_deck.py` |
| Slack upload fails | Make sure `files:write` scope is added |
