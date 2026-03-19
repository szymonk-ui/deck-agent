"""
Superorder Integration Call Deck — Web App
==========================================
Flask web server that serves a browser UI for generating decks.

ENV VARS required:
  PIPEFY_TOKEN          - Your Pipefy personal access token
  PIPEFY_PHASE_ID       - The phase ID for "00OM | Log HQ Info/Send Instructions"
"""

import os, re
from flask import Flask, request, jsonify, send_file, render_template_string
from pipefy_query import get_cards_in_phase, get_card_by_id
from generate_deck import build_deck

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload

PIPEFY_PHASE_ID = os.environ.get("PIPEFY_PHASE_ID", "")

# ── HTML Template ─────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Deck Generator · Superorder</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=DM+Mono:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0a0b;
    --surface: #111113;
    --card: #18181c;
    --border: #2a2a30;
    --border-active: #f4622a;
    --orange: #f4622a;
    --orange-dim: rgba(244,98,42,0.12);
    --orange-glow: rgba(244,98,42,0.25);
    --text: #f0ede8;
    --text-dim: #7a7880;
    --text-mid: #b0acb8;
    --success: #3ecf8e;
    --mono: 'DM Mono', monospace;
    --sans: 'Syne', sans-serif;
    --radius: 12px;
    --radius-sm: 8px;
  }

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  /* Subtle noise texture */
  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 512 512' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");
    pointer-events: none;
    z-index: 0;
    opacity: 0.6;
  }

  header {
    width: 100%;
    max-width: 720px;
    padding: 48px 24px 0;
    position: relative;
    z-index: 1;
  }

  .wordmark {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 40px;
  }

  .wordmark-dot {
    width: 10px;
    height: 10px;
    background: var(--orange);
    border-radius: 50%;
    box-shadow: 0 0 12px var(--orange-glow);
  }

  .wordmark-text {
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-dim);
  }

  h1 {
    font-size: clamp(28px, 5vw, 40px);
    font-weight: 800;
    letter-spacing: -0.02em;
    line-height: 1.1;
    margin-bottom: 10px;
  }

  h1 span { color: var(--orange); }

  .subtitle {
    font-size: 15px;
    color: var(--text-dim);
    font-weight: 400;
    font-family: var(--mono);
    margin-bottom: 48px;
  }

  main {
    width: 100%;
    max-width: 720px;
    padding: 0 24px 80px;
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .step {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 28px;
    transition: border-color 0.2s;
    position: relative;
    overflow: hidden;
  }

  .step.active { border-color: var(--border-active); }
  .step.complete { border-color: #2a2a30; opacity: 0.75; }

  .step-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
  }

  .step-num {
    font-family: var(--mono);
    font-size: 12px;
    font-weight: 500;
    color: var(--orange);
    background: var(--orange-dim);
    border: 1px solid var(--orange-glow);
    border-radius: 6px;
    padding: 3px 8px;
    flex-shrink: 0;
  }

  .step-title {
    font-size: 16px;
    font-weight: 700;
    letter-spacing: -0.01em;
  }

  label {
    display: block;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-dim);
    margin-bottom: 8px;
    font-family: var(--mono);
  }

  .input-row {
    display: flex;
    gap: 10px;
  }

  input[type="text"] {
    flex: 1;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text);
    font-family: var(--mono);
    font-size: 15px;
    padding: 12px 16px;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
    width: 100%;
  }

  input[type="text"]:focus {
    border-color: var(--orange);
    box-shadow: 0 0 0 3px var(--orange-dim);
  }

  input[type="text"]::placeholder { color: var(--text-dim); }

  .btn {
    background: var(--orange);
    color: #fff;
    border: none;
    border-radius: var(--radius-sm);
    padding: 12px 22px;
    font-family: var(--sans);
    font-size: 14px;
    font-weight: 700;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.15s;
    letter-spacing: 0.01em;
  }

  .btn:hover { background: #ff7a44; box-shadow: 0 4px 20px var(--orange-glow); }
  .btn:active { transform: translateY(1px); }
  .btn:disabled { background: #333; color: #666; cursor: not-allowed; box-shadow: none; transform: none; }

  .btn-outline {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-dim);
  }
  .btn-outline:hover { border-color: var(--orange); color: var(--orange); background: var(--orange-dim); box-shadow: none; }

  .btn-lg {
    padding: 16px 32px;
    font-size: 15px;
    width: 100%;
    letter-spacing: 0.02em;
  }

  /* Card preview */
  .card-preview {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 16px 20px;
    margin-top: 16px;
    display: none;
    animation: fadeIn 0.25s ease;
  }

  .card-preview.visible { display: block; }

  .card-preview-name {
    font-size: 17px;
    font-weight: 700;
    margin-bottom: 6px;
  }

  .card-preview-meta {
    font-family: var(--mono);
    font-size: 12px;
    color: var(--text-dim);
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }

  .card-preview-meta span { display: flex; align-items: center; gap: 5px; }

  .tag {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-family: var(--mono);
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 4px;
    background: var(--orange-dim);
    color: var(--orange);
    border: 1px solid var(--orange-glow);
  }

  /* AM selection */
  .am-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  .am-option {
    display: flex;
    align-items: center;
    gap: 12px;
    background: var(--surface);
    border: 2px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 16px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .am-option:hover { border-color: var(--orange); background: var(--orange-dim); }
  .am-option.selected { border-color: var(--orange); background: var(--orange-dim); }

  .am-option input[type="radio"] { display: none; }

  .am-avatar {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: linear-gradient(135deg, #f4622a, #ff9566);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 800;
    color: #fff;
    flex-shrink: 0;
  }

  .am-info-name {
    font-size: 14px;
    font-weight: 700;
  }

  .am-info-role {
    font-size: 11px;
    color: var(--text-dim);
    font-family: var(--mono);
  }

  /* Logo upload */
  .drop-zone {
    border: 2px dashed var(--border);
    border-radius: var(--radius-sm);
    padding: 36px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
    position: relative;
  }

  .drop-zone:hover, .drop-zone.dragover {
    border-color: var(--orange);
    background: var(--orange-dim);
  }

  .drop-zone input[type="file"] {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
    width: 100%;
  }

  .drop-icon {
    font-size: 32px;
    margin-bottom: 10px;
  }

  .drop-label {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 5px;
  }

  .drop-hint {
    font-size: 12px;
    color: var(--text-dim);
    font-family: var(--mono);
  }

  .logo-preview-wrap {
    margin-top: 16px;
    display: none;
    align-items: center;
    gap: 16px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 14px 16px;
    animation: fadeIn 0.25s ease;
  }

  .logo-preview-wrap.visible { display: flex; }

  .logo-preview-wrap img {
    max-height: 56px;
    max-width: 160px;
    object-fit: contain;
    border-radius: 4px;
  }

  .logo-preview-info {
    flex: 1;
    min-width: 0;
  }

  .logo-preview-filename {
    font-family: var(--mono);
    font-size: 12px;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .logo-preview-size {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--text-dim);
    margin-top: 2px;
  }

  .logo-preview-badge {
    font-family: var(--mono);
    font-size: 10px;
    padding: 3px 7px;
    border-radius: 4px;
    background: rgba(62,207,142,0.12);
    color: var(--success);
    border: 1px solid rgba(62,207,142,0.25);
  }

  /* Status messages */
  .status {
    font-family: var(--mono);
    font-size: 13px;
    padding: 10px 14px;
    border-radius: var(--radius-sm);
    margin-top: 14px;
    display: none;
    animation: fadeIn 0.2s ease;
  }

  .status.visible { display: block; }
  .status.error { background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.2); color: #f87171; }
  .status.loading { background: var(--orange-dim); border: 1px solid var(--orange-glow); color: var(--orange); }
  .status.success { background: rgba(62,207,142,0.1); border: 1px solid rgba(62,207,142,0.2); color: var(--success); }

  /* Generate step */
  .generate-section {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 28px;
  }

  .generate-summary {
    display: none;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 16px;
    margin-bottom: 20px;
    font-family: var(--mono);
    font-size: 12px;
    color: var(--text-dim);
    line-height: 1.8;
    animation: fadeIn 0.25s ease;
  }
  .generate-summary.visible { display: block; }
  .generate-summary strong { color: var(--text); font-weight: 500; }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .spinner {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    vertical-align: middle;
    margin-right: 8px;
  }

  .progress-bar {
    height: 2px;
    background: var(--border);
    border-radius: 1px;
    margin-top: 14px;
    overflow: hidden;
    display: none;
  }

  .progress-bar.visible { display: block; }

  .progress-fill {
    height: 100%;
    background: var(--orange);
    border-radius: 1px;
    transition: width 0.4s ease;
    width: 0%;
  }

  footer {
    padding: 24px;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--text-dim);
    text-align: center;
    position: relative;
    z-index: 1;
  }
</style>
</head>
<body>

<header>
  <div class="wordmark">
    <div class="wordmark-dot"></div>
    <span class="wordmark-text">Superorder Internal</span>
  </div>
  <h1>Integration Call<br><span>Deck Generator</span></h1>
  <p class="subtitle">// Pipefy → PPTX in seconds</p>
</header>

<main>

  <!-- STEP 1: Card ID -->
  <div class="step active" id="step1">
    <div class="step-header">
      <span class="step-num">01</span>
      <span class="step-title">Pipefy Card</span>
    </div>
    <label>Card ID</label>
    <div class="input-row">
      <input type="text" id="cardIdInput" placeholder="e.g. 1234567890" autocomplete="off">
      <button class="btn" onclick="fetchCard()">Load</button>
    </div>
    <div class="card-preview" id="cardPreview">
      <div class="card-preview-name" id="previewName"></div>
      <div class="card-preview-meta" id="previewMeta"></div>
    </div>
    <div class="status" id="step1Status"></div>
  </div>

  <!-- STEP 2: AM Selection -->
  <div class="step" id="step2">
    <div class="step-header">
      <span class="step-num">02</span>
      <span class="step-title">Account Manager</span>
    </div>
    <div class="am-grid">
      <label class="am-option" id="amMaanav" onclick="selectAM('maanav')">
        <input type="radio" name="am" value="maanav">
        <div class="am-avatar">MP</div>
        <div>
          <div class="am-info-name">Maanav Patel</div>
          <div class="am-info-role">account manager</div>
        </div>
      </label>
      <label class="am-option" id="amSephra" onclick="selectAM('sephra')">
        <input type="radio" name="am" value="sephra">
        <div class="am-avatar" style="background: linear-gradient(135deg, #a855f7, #ec4899)">SE</div>
        <div>
          <div class="am-info-name">Sephra Engel</div>
          <div class="am-info-role">account manager</div>
        </div>
      </label>
    </div>
  </div>

  <!-- STEP 3: Logo Upload -->
  <div class="step" id="step3">
    <div class="step-header">
      <span class="step-num">03</span>
      <span class="step-title">Chain Logo</span>
    </div>
    <div class="drop-zone" id="dropZone">
      <input type="file" id="logoInput" accept="image/*" onchange="handleLogoChange(this)">
      <div class="drop-icon">⬆</div>
      <div class="drop-label">Drop logo here or click to browse</div>
      <div class="drop-hint">PNG, JPG, SVG, WEBP — will be converted to PNG</div>
    </div>
    <div class="logo-preview-wrap" id="logoPreview">
      <img id="logoPreviewImg" src="" alt="Logo preview">
      <div class="logo-preview-info">
        <div class="logo-preview-filename" id="logoFilename"></div>
        <div class="logo-preview-size" id="logoSize"></div>
      </div>
      <span class="logo-preview-badge">ready</span>
      <button class="btn btn-outline" style="padding: 6px 12px; font-size: 12px;" onclick="clearLogo()">Remove</button>
    </div>
  </div>

  <!-- GENERATE -->
  <div class="generate-section">
    <div class="generate-summary" id="generateSummary"></div>
    <button class="btn btn-lg" id="generateBtn" onclick="generateDeck()" disabled>
      Generate Deck
    </button>
    <div class="progress-bar" id="progressBar">
      <div class="progress-fill" id="progressFill"></div>
    </div>
    <div class="status" id="generateStatus"></div>
  </div>

</main>

<footer>superorder deck generator · internal use only</footer>

<script>
let cardData = null;
let selectedAM = null;
let logoFile = null;

// ── Drag & drop ──────────────────────────────────────────────────────────────
const dz = document.getElementById('dropZone');
dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('dragover'); });
dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
dz.addEventListener('drop', e => {
  e.preventDefault();
  dz.classList.remove('dragover');
  const f = e.dataTransfer.files[0];
  if (f && f.type.startsWith('image/')) applyLogo(f);
});

// ── Fetch card from Pipefy ───────────────────────────────────────────────────
async function fetchCard() {
  const id = document.getElementById('cardIdInput').value.trim();
  if (!id) return;

  showStatus('step1Status', 'loading', '⟳ Fetching card from Pipefy...');

  try {
    const res = await fetch(`/api/card/${id}`);
    const data = await res.json();

    if (!res.ok || data.error) {
      showStatus('step1Status', 'error', '✗ ' + (data.error || 'Card not found'));
      cardData = null;
      updateGenerateBtn();
      return;
    }

    cardData = data;
    showStatus('step1Status', 'success', '✓ Card loaded successfully');
    renderCardPreview(data);
    updateGenerateBtn();
    updateSummary();

  } catch (err) {
    showStatus('step1Status', 'error', '✗ Network error — check Railway logs');
    cardData = null;
  }
}

function renderCardPreview(d) {
  document.getElementById('previewName').textContent = d.chain_name;
  const poc = [d.poc_first_name, d.poc_last_name].filter(Boolean).join(' ') || '—';
  document.getElementById('previewMeta').innerHTML = `
    <span>PoC: ${poc}</span>
    <span>HQ1: ${d.primary_hq_alias || '—'}</span>
    <span>HQ2: ${d.secondary_hq_alias || '—'}</span>
  `;
  document.getElementById('cardPreview').classList.add('visible');
}

// ── AM selection ─────────────────────────────────────────────────────────────
function selectAM(am) {
  selectedAM = am;
  document.getElementById('amMaanav').classList.toggle('selected', am === 'maanav');
  document.getElementById('amSephra').classList.toggle('selected', am === 'sephra');
  updateGenerateBtn();
  updateSummary();
}

// ── Logo handling ────────────────────────────────────────────────────────────
function handleLogoChange(input) {
  if (input.files[0]) applyLogo(input.files[0]);
}

function applyLogo(file) {
  logoFile = file;
  const url = URL.createObjectURL(file);
  document.getElementById('logoPreviewImg').src = url;
  document.getElementById('logoFilename').textContent = file.name;
  document.getElementById('logoSize').textContent = formatBytes(file.size);
  document.getElementById('logoPreview').classList.add('visible');
  updateGenerateBtn();
  updateSummary();
}

function clearLogo() {
  logoFile = null;
  document.getElementById('logoInput').value = '';
  document.getElementById('logoPreview').classList.remove('visible');
  updateGenerateBtn();
  updateSummary();
}

// ── Generate ─────────────────────────────────────────────────────────────────
async function generateDeck() {
  const btn = document.getElementById('generateBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Generating...';

  const pb = document.getElementById('progressBar');
  const pf = document.getElementById('progressFill');
  pb.classList.add('visible');
  pf.style.width = '20%';

  showStatus('generateStatus', 'loading', '⟳ Building your deck...');

  try {
    const form = new FormData();
    form.append('card_id', cardData.id);
    form.append('am', selectedAM);
    if (logoFile) form.append('logo', logoFile);

    pf.style.width = '50%';

    const res = await fetch('/api/generate', { method: 'POST', body: form });

    pf.style.width = '85%';

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Unknown error');
    }

    pf.style.width = '100%';

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const safeName = (cardData.chain_name || 'deck').replace(/[^a-z0-9]/gi, '_');
    a.href = url;
    a.download = `${safeName}_Integration_Call_Deck.pptx`;
    a.click();

    showStatus('generateStatus', 'success', '✓ Deck downloaded!');

  } catch (err) {
    showStatus('generateStatus', 'error', '✗ ' + err.message);
    pf.style.width = '0%';
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Generate Deck';
    setTimeout(() => { pb.classList.remove('visible'); pf.style.width = '0%'; }, 1500);
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function updateGenerateBtn() {
  const ready = cardData && selectedAM;
  document.getElementById('generateBtn').disabled = !ready;
}

function updateSummary() {
  const el = document.getElementById('generateSummary');
  if (!cardData && !selectedAM && !logoFile) { el.classList.remove('visible'); return; }

  const amName = selectedAM === 'maanav' ? 'Maanav Patel' : selectedAM === 'sephra' ? 'Sephra Engel' : '—';
  const lines = [
    cardData ? `<strong>Chain:</strong> ${cardData.chain_name}` : '',
    selectedAM ? `<strong>AM:</strong> ${amName}` : '',
    logoFile  ? `<strong>Logo:</strong> ${logoFile.name} (→ PNG)` : '<strong>Logo:</strong> none',
  ].filter(Boolean);

  el.innerHTML = lines.join('<br>');
  el.classList.add('visible');
}

function showStatus(id, type, msg) {
  const el = document.getElementById(id);
  el.className = `status ${type} visible`;
  el.textContent = msg;
}

function formatBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1024*1024) return (b/1024).toFixed(1) + ' KB';
  return (b/(1024*1024)).toFixed(1) + ' MB';
}

// Enter key on card ID input
document.getElementById('cardIdInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') fetchCard();
});
</script>
</body>
</html>"""

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/card/<card_id>")
def api_card(card_id):
    try:
        card = get_card_by_id(card_id)
        if not card:
            return jsonify({"error": "Card not found"}), 404
        return jsonify(card)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/generate", methods=["POST"])
def api_generate():
    card_id = request.form.get("card_id", "").strip()
    am = request.form.get("am", "").strip()
    logo_file = request.files.get("logo")

    if not card_id or am not in ("maanav", "sephra"):
        return jsonify({"error": "Missing card_id or am"}), 400

    try:
        card = get_card_by_id(card_id)
        if not card:
            return jsonify({"error": "Card not found"}), 404

        # Save logo temporarily if provided
        logo_path = None
        if logo_file and logo_file.filename:
            import tempfile, os
            suffix = os.path.splitext(logo_file.filename)[-1] or ".png"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            logo_file.save(tmp.name)
            logo_path = tmp.name

        am_name = "Maanav Patel" if am == "maanav" else "Sephra Engel"

        output_path = build_deck(
            company_name=card["chain_name"],
            deal_name=card["chain_name"],
            hq_email_1=card["primary_hq_alias"],
            hq_email_2=card["secondary_hq_alias"],
            poc_name=f"{card['poc_first_name']} {card['poc_last_name']}".strip(),
            am_name=am_name,
            agenda_variant=am,
            logo_path=logo_path,
        )

        if logo_path:
            os.unlink(logo_path)

        import re as _re
        safe = _re.sub(r"[^\w\s-]", "", card["chain_name"]).strip().replace(" ", "_")
        return send_file(
            output_path,
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            as_attachment=True,
            download_name=f"{safe}_Integration_Call_Deck.pptx"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(port=3000, debug=True)
