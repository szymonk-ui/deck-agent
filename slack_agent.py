"""
Superorder Integration Call Deck — Slack Agent
=============================================
This is a Flask webhook server that powers the Slack bot conversation.
Deploy this to Railway, Render, or any Python host.

Flow:
  1. User DMs "generate deck" (or any message) to the Slack app
  2. Bot queries Pipefy for 00OM cards → posts numbered list to Slack
  3. User replies with a number
  4. Bot asks: Maanav or Sephra?
  5. User replies
  6. Bot generates PPTX from template → uploads to Slack

ENV VARS required:
  SLACK_BOT_TOKEN       - Your Slack bot OAuth token (xoxb-...)
  SLACK_SIGNING_SECRET  - From Slack app settings (for request verification)
  PIPEFY_TOKEN          - Your Pipefy personal access token
  PIPEFY_PHASE_ID       - The phase ID for "00OM | Log HQ Info/Send Instructions"
"""

import os, json, hmac, hashlib, time, re, requests, threading
from flask import Flask, request, jsonify
from pipefy_query import get_cards_in_phase
from generate_deck import build_deck  # see generate_deck.py

app = Flask(__name__)

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_SIGNING_SECRET = os.environ["SLACK_SIGNING_SECRET"]
PIPEFY_PHASE_ID = os.environ["PIPEFY_PHASE_ID"]  # e.g. "325457365"

# In-memory session store per user DM (user_id -> state dict)
# For production, use Redis or a DB
SESSIONS = {}

# ── Slack helpers ────────────────────────────────────────────────────────────

def slack_post(channel, text, thread_ts=None):
    payload = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    r = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json=payload
    )
    return r.json()

def slack_upload_file(channel, filepath, filename, title):
    """Upload a file to Slack using the new files.getUploadURLExternal flow."""
    file_size = os.path.getsize(filepath)
    
    # Step 1: Get upload URL
    r = requests.post(
        "https://slack.com/api/files.getUploadURLExternal",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        data={"filename": filename, "length": file_size}
    )
    url_data = r.json()
    upload_url = url_data["upload_url"]
    file_id = url_data["file_id"]
    
    # Step 2: Upload file bytes
    with open(filepath, "rb") as f:
        requests.post(upload_url, data=f)
    
    # Step 3: Complete upload
    requests.post(
        "https://slack.com/api/files.completeUploadExternal",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json={"files": [{"id": file_id, "title": title}], "channel_id": channel}
    )

def verify_slack_signature(req):
    """Verify request actually came from Slack."""
    ts = req.headers.get("X-Slack-Request-Timestamp", "")
    sig = req.headers.get("X-Slack-Signature", "")
    if abs(time.time() - int(ts)) > 300:
        return False
    base = f"v0:{ts}:{req.get_data(as_text=True)}"
    expected = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(), base.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig)

# ── Conversation state machine ───────────────────────────────────────────────

def handle_message(user_id, channel_id, text, thread_ts=None):
    """Main state machine — called in a background thread."""
    session = SESSIONS.get(user_id, {})
    state = session.get("state", "idle")
    text_clean = text.strip().lower()

    # ── IDLE: start a new session ────────────────────────────────────────────
    if state == "idle" or any(kw in text_clean for kw in ["generate", "deck", "start", "new"]):
        slack_post(channel_id, "🔍 Scanning Pipefy for chains in *00OM | Log HQ Info/Send Instructions*...")
        
        try:
            phase_name, cards = get_cards_in_phase(PIPEFY_PHASE_ID)
        except Exception as e:
            slack_post(channel_id, f"❌ Pipefy error: {e}")
            return
        
        if not cards:
            slack_post(channel_id, "📭 No chains currently in *00OM* phase.")
            return
        
        lines = [f"*Chains in 00OM — pick a number:*\n"]
        for i, card in enumerate(cards, 1):
            poc = f"{card['poc_first_name']} {card['poc_last_name']}".strip()
            lines.append(f"`{i}.` *{card['chain_name']}*  — PoC: {poc or '—'}")
        
        lines.append("\nReply with the number of the chain you want to generate a deck for.")
        slack_post(channel_id, "\n".join(lines))
        
        SESSIONS[user_id] = {
            "state": "awaiting_chain_selection",
            "cards": cards,
            "channel_id": channel_id
        }
        return

    # ── AWAITING CHAIN SELECTION ─────────────────────────────────────────────
    if state == "awaiting_chain_selection":
        cards = session["cards"]
        try:
            idx = int(text_clean) - 1
            assert 0 <= idx < len(cards)
        except:
            slack_post(channel_id, f"Please reply with a number between 1 and {len(cards)}.")
            return
        
        chosen = cards[idx]
        SESSIONS[user_id] = {**session, "state": "awaiting_am", "chosen_card": chosen}
        
        slack_post(
            channel_id,
            f"✅ Got it — *{chosen['chain_name']}*\n\n"
            f"Who is the Account Manager?\n`1.` Maanav Patel\n`2.` Sephra Engel"
        )
        return

    # ── AWAITING AM SELECTION ────────────────────────────────────────────────
    if state == "awaiting_am":
        chosen_card = session["chosen_card"]
        
        if text_clean in ["1", "maanav", "maanav patel"]:
            am = "Maanav Patel"
            agenda_variant = "maanav"   # use slide 2 (keeps Maanav photo)
        elif text_clean in ["2", "sephra", "sephra engel"]:
            am = "Sephra Engel"
            agenda_variant = "sephra"   # use slide 3 (keeps Sephra photo)
        else:
            slack_post(channel_id, "Reply `1` for Maanav or `2` for Sephra.")
            return
        
        slack_post(channel_id, f"⚙️ Generating deck for *{chosen_card['chain_name']}* with AM *{am}*...")
        
        try:
            output_path = build_deck(
                company_name=chosen_card["chain_name"],
                deal_name=chosen_card["chain_name"],
                hq_email_1=chosen_card["primary_hq_alias"],
                hq_email_2=chosen_card["secondary_hq_alias"],
                poc_name=f"{chosen_card['poc_first_name']} {chosen_card['poc_last_name']}".strip(),
                am_name=am,
                agenda_variant=agenda_variant,
            )
            filename = os.path.basename(output_path)
            slack_upload_file(channel_id, output_path, filename, f"Integration Call Deck — {chosen_card['chain_name']}")
            slack_post(channel_id, f"✅ Done! Here's the deck for *{chosen_card['chain_name']}*.")
        except Exception as e:
            slack_post(channel_id, f"❌ Error generating deck: {e}")
        
        SESSIONS.pop(user_id, None)
        return

    # ── FALLBACK ─────────────────────────────────────────────────────────────
    slack_post(channel_id, 'Say *"generate deck"* to start.')

# ── Webhook endpoint ─────────────────────────────────────────────────────────

@app.route("/slack/events", methods=["POST"])
def slack_events():
    # URL verification challenge (first-time setup)
    body = request.get_json()
    if body.get("type") == "url_verification":
        return jsonify({"challenge": body["challenge"]})

    if not verify_slack_signature(request):
        return "Unauthorized", 401

    event = body.get("event", {})
    
    # Only handle DMs (channel_type == "im") to avoid loops
    if event.get("type") != "message":
        return "ok"
    if event.get("bot_id"):  # ignore bot's own messages
        return "ok"
    if event.get("channel_type") not in ("im", "mpim"):
        return "ok"  # only DMs — change to "channel" if you want it in a channel

    user_id = event["user"]
    channel_id = event["channel"]
    text = event.get("text", "")
    thread_ts = event.get("thread_ts")

    # Respond immediately, process in background (Slack requires <3s response)
    threading.Thread(
        target=handle_message,
        args=(user_id, channel_id, text, thread_ts),
        daemon=True
    ).start()

    return "ok"

if __name__ == "__main__":
    app.run(port=3000, debug=True)
