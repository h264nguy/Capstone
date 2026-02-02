from __future__ import annotations

import json

# -------------------------
# Ingredient labels (normalized id -> display)
# -------------------------
INGREDIENT_LABELS = {
  "coca_cola": "Coca-Cola",
  "red_bull": "Red Bull",
  "ginger_ale": "Ginger Ale",
  "orange_juice": "Orange Juice",
  "sprite": "Sprite",
  "water": "Water",
  "lemonade": "Lemonade",
  "splash_of_water": "Splash of Water",
  "splash_of_sprite": "Splash of Sprite",
}

def pretty_ingredient(ing: str) -> str:
    if not ing:
        return ""
    return INGREDIENT_LABELS.get(ing, ing.replace("_"," ").title())
from collections import Counter
from pathlib import Path
from string import Template

from fastapi import APIRouter, Request, Request
from fastapi.responses import HTMLResponse, RedirectResponse, RedirectResponse

from app.core.auth import current_user
from app.core.storage import ensure_drinks_file, load_drinks, load_orders
from app.ml.recommender import recommend_for_user

router = APIRouter()

# ---- Read the SAME orders.json used by orders_routes.py ----
REPO_ROOT = Path(__file__).resolve().parents[2]  # app/routers -> app -> repo_root
DATA_DIR = REPO_ROOT / "data"
ORDERS_FILE = DATA_DIR / "orders.json"


def _load_orders_shared():
    """Load orders written by /checkout."""
    return load_orders()


STYLE = """
<style>
*{box-sizing:border-box}
body{
  margin:0; padding:0;
  font-family: "Playfair Display", serif;
  background:#000;
  background-image:url('/static/background-1.png');
  background-size:cover;
  background-position:center;
  background-repeat:no-repeat;
  background-attachment:fixed;
  color:#1f130d;
}
a{color:#f5e6d3}
.page{max-width:1100px;margin:0 auto;padding:40px 20px 60px}
h1{
  font-size:46px; letter-spacing:3px;
  text-align:center; margin:0 0 6px;
  color:#f5e6d3;
  text-shadow:0 0 10px rgba(245,230,211,.65),
             0 0 22px rgba(245,230,211,.45),
             0 0 34px rgba(255,190,130,.25);
}
.grid{display:grid;gap:14px}
.cards{grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}
.card{
  background:rgba(0,0,0,.55);
  border:1px solid rgba(245,230,211,.25);
  border-radius:18px;
  padding:18px;
  box-shadow:0 10px 30px rgba(0,0,0,.35);
}
.card.selected{
  border-color: rgba(255,190,130,.65);
  box-shadow: 0 0 0 1px rgba(255,190,130,.25), 0 14px 36px rgba(0,0,0,.45);
}
.card h2{margin:0 0 10px;color:#f5e6d3;letter-spacing:2px}
.btnrow{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
.corner-actions{position:fixed;top:24px;left:0;right:0;pointer-events:none;z-index:50}
.corner{pointer-events:auto;position:fixed;top:24px}
.corner.left{left:24px}
.corner.right{right:24px}
@media(max-width:520px){.corner.left{left:14px}.corner.right{right:14px}.corner{top:14px}}

button,.primary,.secondary{
  appearance:none;border:0;cursor:pointer;
  padding:12px 14px;border-radius:14px;
  font-family:inherit;
  font-weight:700;
  letter-spacing:1px;
}
button[disabled]{opacity:.45;cursor:not-allowed;filter:saturate(.6)}
.btn-active{background:#f5e6d3;color:#1f130d}
.primary{background:#f5e6d3;color:#1f130d}
.secondary{background:rgba(0,0,0,.35);color:#f5e6d3;border:1px solid rgba(245,230,211,.25);text-decoration:none;display:inline-block}
.small{color:rgba(245,230,211,.85)}
hr{border:0;border-top:1px solid rgba(245,230,211,.18);margin:14px 0}
.table{width:100%;border-collapse:collapse;margin-top:10px}
.table th,.table td{border-bottom:1px solid rgba(245,230,211,.18);padding:10px 8px;color:#f5e6d3;text-align:left}
.table th{color:rgba(245,230,211,.92)}
.pill{display:inline-block;padding:6px 10px;border-radius:999px;background:rgba(245,230,211,.12);border:1px solid rgba(245,230,211,.18);color:#f5e6d3;font-size:12px}
.qty-pill{min-width:44px;text-align:center;display:inline-flex;align-items:center;justify-content:center}
.ing{margin-top:10px;color:rgba(245,230,211,.9)}
.ing ul{margin:8px 0 0 18px;padding:0}
.ing li{margin:4px 0;color:rgba(245,230,211,.85)}

/* --- ETA live countdown bar --- */
.etaBox{
  margin-top:12px;
  padding:12px 14px;
  border:1px solid rgba(245,230,211,.25);
  border-radius:14px;
  background:rgba(0,0,0,.35);
  color:#f5e6d3;
}
.etaTop{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.etaLabel{letter-spacing:.14em;font-weight:700;font-size:12px;opacity:.9}
.etaText{font-size:14px;opacity:.95}
.etaBarBg{
  margin-top:10px;
  height:10px;
  border-radius:999px;
  background:rgba(245,230,211,.18);
  overflow:hidden;
}
.etaBarFill{
  height:100%;
  border-radius:999px;
  background:rgba(245,230,211,.85);
  transition:width .35s linear;
}


/* Separate top-left buttons (History + Logout) */
.corner.left{left:18px;}
.corner.left2{left:138px;}


.btn.secondary{background:transparent;color:#f5e6d3;border:1px solid rgba(245,230,211,.35)}
</style>
"""


def _require_user(request: Request):
    return current_user(request)


def _top_drinks_for_user(username: str, limit: int = 3):
    # IMPORTANT: use shared orders file (same one /checkout writes)
    orders = _load_orders_shared()
    c = Counter()
    for o in orders:
        if str(o.get("username")) == str(username):
            c[str(o.get("drinkName", ""))] += int(o.get("quantity", 1) or 1)
    return [name for name, _ in c.most_common(limit) if name]


def _find_drink(drink_id: str):
    ensure_drinks_file()
    for d in load_drinks():
        if d.get("id") == drink_id:
            return d
    return None




@router.get('/guest')
def guest_login(request: Request):
    # Guest session: recommendations remain default (non-personalized)
    request.session['user'] = 'guest'
    request.session['is_guest'] = True
    return RedirectResponse(url='/', status_code=302)


@router.get('/logout')
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url='/login', status_code=302)

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return RedirectResponse("/builder" if current_user(request) else "/login", status_code=302)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    return HTMLResponse(f"""
    <html><head><title>Dashboard</title>{STYLE}</head>
    <body><div class='page'>
      <h1>DASHBOARD</h1>
      <div style='text-align:center; margin-bottom:14px;'>
        <span class='pill'>Welcome, {user}</span>
      </div>

      <div class='grid cards'>
        <div class='card'>
          <h2>HISTORY</h2>
          <div class='small'>See what you ordered before.</div>
          <div class='btnrow'>
            <button class='secondary' onclick="window.location.href='/history'">View History</button>
          </div>
        </div>

        <div class='card'>
          <h2>RECOMMEND</h2>
          <div class='small'>New drink suggestions.</div>
          <div class='btnrow'>
            <button class='secondary' onclick="window.location.href='/recommendations'">See Recommendations</button>
          </div>
        </div>


      </div>

      <div class='btnrow' style='margin-top:14px'>
        <button class='secondary' onclick="window.location.href='/logout'">Logout</button>
      </div>
    </div></body></html>
    """)


@router.get("/menu", response_class=HTMLResponse)
def menu_alias(request: Request):
    return RedirectResponse("/builder", status_code=302)


@router.get("/builder", response_class=HTMLResponse)
def builder(request: Request):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    ensure_drinks_file()

    tpl = Template(r"""
<html><head><title>Builder</title>$STYLE</head>
<body><div class='page'>
  <h1>SMART BARTENDER</h1>
  <div class='card'>
    <h2>RECOMMENDED FOR YOU</h2>
    <div id='recs' class='grid cards' style='margin-top:14px'></div>
    <hr/>
    <h2>MENU</h2>
    <div class='small'>Pick drinks and quantities. Then checkout to save history (and optionally send to ESP).</div>
    <div id='menu' class='grid cards' style='margin-top:14px'></div>

    <hr/>
    <h2>CART</h2>
    <div id='cart' class='small'>No items yet.</div>
    <div id='status' class='small' style='margin-top:10px'></div>
    <div id='etaBox' class='etaBox' style='display:none;'>
      <div class='etaTop'>
        <div class='etaLabel'>ETA</div>
        <div id='etaText' class='etaText'>--</div>
      </div>
      <div class='etaBarBg'>
        <div id='etaBarFill' class='etaBarFill' style='width:0%'></div>
      </div>
    </div>

  </div>

  <div class='corner-actions'>
    <a class='secondary corner left' href='/history'>History</a>
    <a class='secondary corner left2' href='/logout'>Logout</a>
    <button class='primary corner right' onclick='checkout()'>Checkout</button>
  </div>


<script>
let drinks = [];
let cart = {};
let recs = [];
let pollTimer = null;

function formatETA(sec){
  try{ sec = Math.max(0, parseInt(sec)); }catch(e){ return String(sec); }
  const m = Math.floor(sec/60);
  const s = sec%60;
  return m>0 ? `${m}m ${s.toString().padStart(2,'0')}s` : `${s}s`;
}

function parseEtaSeconds(v){
  if(v === null || v === undefined) return null;
  if(typeof v === 'number') return isFinite(v) ? Math.max(0, Math.floor(v)) : null;
  // try plain int string
  const n = parseInt(v);
  if(!isNaN(n) && String(v).trim().match(/^\d+$/)) return Math.max(0, n);
  // try formats like "10m 06s" or "10m06s" or "1m" or "45s"
  const s = String(v);
  const mm = s.match(/(\d+)\s*m/i);
  const ss = s.match(/(\d+)\s*s/i);
  if(mm || ss){
    const m = mm ? parseInt(mm[1]) : 0;
    const sec = ss ? parseInt(ss[1]) : 0;
    return Math.max(0, m*60 + sec);
  }
  return null;
}

function setEtaFromServer(etaSeconds, etaAheadSeconds){
  const serverEtaRaw = parseEtaSeconds(etaSeconds);
  if(serverEtaRaw === null) return; // don't overwrite with invalid

  const serverEta = Math.max(0, serverEtaRaw);

  const currentOrderId = localStorage.getItem('lastOrderId');
  const etaOrderId = localStorage.getItem('etaOrderId');
  if(currentOrderId && etaOrderId && currentOrderId !== etaOrderId){
    // new order detected; clear stale ETA state
    localStorage.setItem('etaOrderId', currentOrderId);
    localStorage.removeItem('etaInitial');
    localStorage.removeItem('etaRemaining');
    localStorage.removeItem('etaUpdatedTs');
    localStorage.removeItem('etaAheadSeconds');
  }

  const hasPrev = !!localStorage.getItem('etaUpdatedTs');

  // Current live remaining (based on our last tick)
  const live = getLiveEta();
  const liveRemaining = (live && live.remaining !== undefined) ? Math.max(0, live.remaining) : null;

  // Make ETA monotonic (never jump upward due to server jitter) ONLY after we have a previous sample.
  // (First sample should always be accepted; otherwise we can get stuck at 0.)
  let nextRemaining = serverEta;
  if(hasPrev && liveRemaining !== null){
    // Allow tiny upward corrections (<=2s).
    if(serverEta > liveRemaining + 2){
      nextRemaining = Math.ceil(liveRemaining);
    } else {
      nextRemaining = serverEta;
    }
  }

  // Initial baseline: set once per order.
  const prevInitial = parseInt(localStorage.getItem('etaInitial') || '0');
  if(!prevInitial){
    localStorage.setItem('etaInitial', String(Math.max(1, nextRemaining)));
  } else {
    localStorage.setItem('etaInitial', String(Math.max(1, prevInitial)));
  }

  localStorage.setItem('etaRemaining', String(Math.max(0, nextRemaining)));
  localStorage.setItem('etaUpdatedTs', String(Date.now()));

  // Smooth "starts in" (ahead) if provided
  const serverAheadRaw = parseEtaSeconds(etaAheadSeconds);
  if(serverAheadRaw !== null){
    const serverAhead = Math.max(0, serverAheadRaw);
    const prevAhead = parseInt(localStorage.getItem('etaAheadSeconds') || '0');
    // never jump upward (allow +2s) once we have a previous sample
    const nextAhead = (prevAhead && serverAhead > prevAhead + 2) ? prevAhead : serverAhead;
    localStorage.setItem('etaAheadSeconds', String(nextAhead));
  }

  const box = document.getElementById('etaBox');
  if(box) box.style.display = 'block';
}

function getLiveEta(){
  const remaining0 = parseFloat(localStorage.getItem('etaRemaining') || '0');
  const ts = parseFloat(localStorage.getItem('etaUpdatedTs') || '0');
  if(!ts) return {remaining: remaining0, initial: parseFloat(localStorage.getItem('etaInitial')||'0')};
  const elapsed = (Date.now() - ts) / 1000.0;
  const remaining = Math.max(0, remaining0 - elapsed);
  const initial = parseFloat(localStorage.getItem('etaInitial') || String(Math.max(1, remaining0)));
  return {remaining, initial};
}

function renderEtaBar(){
  const box = document.getElementById('etaBox');
  if(!box) return;

  const lastOrderId = localStorage.getItem('lastOrderId');
  if(!lastOrderId){
    box.style.display = 'none';
    return;
  }

  const {remaining, initial} = getLiveEta();
  const aheadStored = parseEtaSeconds(localStorage.getItem('etaAheadSeconds'));
  if((!initial || initial<=0) && aheadStored && aheadStored>0){
    box.style.display = 'block';
    const etaText = document.getElementById('etaText');
    if(etaText) etaText.innerText = `Waiting for ETA... (starts in ~${formatETA(aheadStored)})`;
    const fill = document.getElementById('etaBarFill');
    if(fill) fill.style.width = '0%';
    return;
  }

  if(!initial){
    box.style.display = 'none';
    return;
  }

  box.style.display = 'block';

  const pct = Math.max(0, Math.min(100, (1 - (remaining/initial)) * 100));
  const fill = document.getElementById('etaBarFill');
  if(fill) fill.style.width = pct.toFixed(1) + '%';

  const startsIn = localStorage.getItem('etaAheadSeconds');
  const startsTxt = (startsIn !== null && startsIn !== undefined && startsIn !== '') 
    ? ` (starts in ~${formatETA(parseInt(startsIn))})` 
    : '';

  const etaText = document.getElementById('etaText');
  if(etaText) etaText.innerText = `${formatETA(Math.ceil(remaining))}${startsTxt}`;
}

function startEtaTicker(){
  // One global ticker tied to page
  if(window.__etaTicker) clearInterval(window.__etaTicker);
  window.__etaTicker = setInterval(renderEtaBar, 500);
  renderEtaBar();
}



function ingredientsHtml(d){
  const arr = d && d.ingredients;
  if(!arr || !Array.isArray(arr) || arr.length===0) return "";
  const items = arr.map(x => `<li>${String(x)}</li>`).join("");
  return `<div class='ing'><div class='small'>Ingredients:</div><ul>${items}</ul></div>`;
}

function renderRecs(){
  const el = document.getElementById('recs');
  if(!el) return;
  el.innerHTML='';
  if(!recs || recs.length===0){ el.innerHTML = "<div class='small'>No recommendations yet. Place a few orders first 🙂</div>"; return; }
  recs.forEach(d => {
    const card = document.createElement('div');
    const qty = (cart[d.id] && cart[d.id].quantity) ? cart[d.id].quantity : 0;
    card.className = qty > 0 ? 'card selected' : 'card';
    const cal = (d.calories || 0);
    card.innerHTML = `
      <h2>${d.name}</h2>
      <div class='small'>Calories: <span class='pill'>${cal} cal</span></div>
      <div class='small' style='margin-top:10px'>In cart: <span class='pill qty-pill'>${qty}</span></div>
      ${ingredientsHtml(d)}
      <div class='btnrow' style='margin-top:12px'>
        <button class='secondary ${qty>0 ? 'btn-active' : ''}' onclick="addToCart('${d.id}','${d.name.replace(/'/g, "\\'")}',${cal})">Add</button>
        <button class='secondary' ${qty===0 ? 'disabled' : ''} onclick="removeFromCart('${d.id}')">Remove</button>
        
      </div>
    `;
    el.appendChild(card);
  })
}

function renderMenu(){
  const el = document.getElementById('menu');
  el.innerHTML = '';
  drinks.forEach(d => {
    const card = document.createElement('div');
    const qty = (cart[d.id] && cart[d.id].quantity) ? cart[d.id].quantity : 0;
    card.className = qty > 0 ? 'card selected' : 'card';
    const cal = (d.calories || 0);
    card.innerHTML = `
      <h2>${d.name}</h2>
      <div class='small'>Calories: <span class='pill'>${cal} cal</span></div>
      <div class='small' style='margin-top:10px'>In cart: <span class='pill qty-pill'>${qty}</span></div>
      ${ingredientsHtml(d)}
      <div class='btnrow' style='margin-top:12px'>
        
        <button class='secondary ${qty>0 ? 'btn-active' : ''}' onclick="addToCart('${d.id}','${d.name.replace(/'/g, "\\'")}',${cal})">Add</button>
        <button class='secondary' ${qty===0 ? 'disabled' : ''} onclick="removeFromCart('${d.id}')">Remove</button>
      </div>
    `;
    el.appendChild(card);
  })
}

function renderCart(){
  const el = document.getElementById('cart');
  const keys = Object.keys(cart);
  if(keys.length===0){ el.innerHTML='No items yet.'; return; }
  let html = '<table class="table"><tr><th>Drink</th><th>Qty</th><th>Calories</th></tr>';
  keys.forEach(k=>{
    const it = cart[k];
    html += `<tr><td>${it.drinkName}</td><td>${it.quantity}</td><td>${it.calories}</td></tr>`;
  })
  html += '</table>';
  el.innerHTML = html;
}

function addToCart(id,name,cal){
  if(!cart[id]) cart[id] = {drinkId:id, drinkName:name, quantity:0, calories:cal};
  cart[id].quantity += 1;
  renderCart();
  renderMenu();
  renderRecs();
}

function removeFromCart(id){
  if(!cart[id]) return;
  cart[id].quantity -= 1;
  if(cart[id].quantity <= 0) delete cart[id];
  renderCart();
  renderMenu();
  renderRecs();
}

async function checkout(){
  const status = document.getElementById('status');
  status.innerText = 'Checking out...';
  const items = Object.values(cart);
  if(items.length===0){ status.innerText='Cart is empty.'; return; }

  const res = await fetch('/checkout', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({items})
  });

  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) {
    await res.text();
    status.innerText = "Checkout failed (server returned non-JSON). Please login again.";
    return;
  }

  const data = await res.json();
  if (!res.ok || !data.ok) {
    status.innerText = "Error: " + (data.error || ("HTTP " + res.status));
    return;
  }

  // persist last order so ETA survives refresh
  localStorage.setItem('lastOrderId', data.orderId);
  localStorage.setItem('lastOrderTs', String(Date.now()));
  // reset ETA state for a new order (prevents stale 0s from previous order)
  localStorage.setItem('etaOrderId', data.orderId);
  localStorage.removeItem('etaInitial');
  localStorage.removeItem('etaRemaining');
  localStorage.removeItem('etaUpdatedTs');
  localStorage.removeItem('etaAheadSeconds');
        localStorage.removeItem('etaOrderId');
  cart = {};
  renderCart();
  const q = (data.queue || {});
  if (q.position) {
    const eta = (q.etaSeconds!==undefined) ? formatETA(q.etaSeconds) : '...';
    const etaStart = (q.etaAheadSeconds!==undefined) ? formatETA(q.etaAheadSeconds) : '...';
    status.innerText = `Queued! Position #${q.position} (ahead: ${q.ahead}). ETA: ${eta} (starts in ~${etaStart}). Order ID: ${data.orderId}`;
    setEtaFromServer(q.etaSeconds, q.etaAheadSeconds);
    startQueuePoll(data.orderId);
    startEtaTicker();
  } else {
    status.innerText = `Order saved. Order ID: ${data.orderId}`;
  }
}

function startQueuePoll(orderId){
  if(pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async ()=>{
    try{
      const r = await fetch(`/api/queue/status?orderId=${encodeURIComponent(orderId)}`);
      const data = await r.json();
      if(data && data.ok){
        const eta = (data.etaSeconds!==undefined) ? formatETA(data.etaSeconds) : '...';
        const etaStart = (data.etaAheadSeconds!==undefined) ? formatETA(data.etaAheadSeconds) : '...';
        document.getElementById('status').innerText = `Queued! Position #${data.position} (ahead: ${data.ahead}). Status: ${data.status}. ETA: ${eta} (starts in ~${etaStart}). Order ID: ${orderId}`;
        setEtaFromServer(data.etaSeconds, data.etaAheadSeconds);
      } else {
        document.getElementById('status').innerText = `Order completed (or removed from queue). Order ID: ${orderId}`;
        clearInterval(pollTimer);
        localStorage.removeItem('lastOrderId');
        localStorage.removeItem('lastOrderTs');
        localStorage.removeItem('etaInitial');
        localStorage.removeItem('etaRemaining');
        localStorage.removeItem('etaUpdatedTs');
        localStorage.removeItem('etaAheadSeconds');
      }
    }catch(e){ /* ignore */ }
  }, 3000);
}

(async function init(){
  const r = await fetch('/api/drinks');
  drinks = await r.json();
  const lastOrderId = localStorage.getItem('lastOrderId');
  if(lastOrderId){
    document.getElementById('status').innerText = `Resuming status for Order ID: ${lastOrderId}...`;
    startQueuePoll(lastOrderId);
    startEtaTicker();
  }
  try{
    const rr = await fetch('/api/recommendations?k=5');
    const rdata = await rr.json();
    if(rdata && rdata.ok) recs = rdata.recommendations || [];
  }catch(e){}
  renderRecs();
  renderMenu();
  renderCart();
})();
</script>

</div></body></html>
""")

    return HTMLResponse(tpl.safe_substitute(STYLE=STYLE))


@router.get("/drink/{drink_id}", response_class=HTMLResponse)
def drink_page(request: Request, drink_id: str):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    d = _find_drink(drink_id)
    if not d:
        return HTMLResponse(
            f"<html><head><title>Not Found</title>{STYLE}</head>"
            f"<body><div class='page'><h1>NOT FOUND</h1>"
            f"<div class='card'><p class='small'>Unknown drink id: <b>{drink_id}</b></p>"
            f"<div class='btnrow'><button class='secondary' onclick=\"window.location.href='/builder'\">Back</button></div>"
            f"</div></div></body></html>",
            status_code=404
        )

    name = d.get("name", drink_id)
    cal = int(d.get("calories", 0) or 0)

    ingredients = d.get("ingredients")
    if isinstance(ingredients, list) and ingredients:
        lis = "".join([f"<li>{str(x)}</li>" for x in ingredients])
        ingredients_block = f"<div class='ing' style='margin-top:12px'><div class='small'>Ingredients:</div><ul>{lis}</ul></div>"
    else:
        ingredients_block = ""

    tpl = Template(r"""
<html><head><title>$name</title>$STYLE</head>
<body><div class='page'>
  <h1>$name_upper</h1>
  <div class='grid cards'>
    <div class='card'>
      <h2>ORDER THIS DRINK</h2>
      <div class='small'>Calories: <span class='pill'>$cal cal</span></div>
      $ingredients_block
      <hr/>
      <div class='small'>Quantity</div>
      <div class='btnrow'>
        <button class='secondary' onclick='decQty()'>-</button>
        <span id='qty' class='pill qty-pill'>1</span>
        <button class='secondary' onclick='incQty()'>+</button>
      </div>
      <div class='btnrow' style='margin-top:14px'>
        <button class='primary' onclick='checkout()'>Checkout</button>
        <button class='secondary' onclick="window.location.href='/builder'">Menu</button>
      </div>
      <div id='status' class='small' style='margin-top:10px'></div>
    </div>
  </div>

<script>
let quantity = 1;
function setQty(){ document.getElementById('qty').innerText = quantity; }
function incQty(){ quantity += 1; setQty(); }
function decQty(){ quantity = Math.max(1, quantity - 1); setQty(); }

async function checkout(){
  const status = document.getElementById('status');
  status.innerText = 'Checking out...';
  const items = [{drinkId: "$drink_id", drinkName: "$name_js", quantity: quantity, calories: $cal}];

  const res = await fetch('/checkout', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({items})
  });

  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) {
    await res.text();
    status.innerText = "Checkout failed (server returned non-JSON). Please login again.";
    return;
  }

  const data = await res.json();
  if (!res.ok || !data.ok) {
    status.innerText = "Error: " + (data.error || ("HTTP " + res.status));
    return;
  }

  const q = (data.queue || {});
  if (q.position) {
    status.innerText = `Queued! Position #${q.position} (ahead: ${q.ahead}). Order ID: ${data.orderId}`;
    startQueuePoll(data.orderId);
  } else {
    status.innerText = `Order saved. Order ID: ${data.orderId}`;
  }
}

setQty();
</script>

</div></body></html>
""")

    return HTMLResponse(tpl.safe_substitute(
        STYLE=STYLE,
        name=name,
        name_upper=name.upper(),
        name_js=name.replace('"', '\\"'),
        drink_id=drink_id,
        cal=str(cal),
        ingredients_block=ingredients_block,
    ))


@router.get("/history", response_class=HTMLResponse)
def history(request: Request):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    tpl = Template(r"""
<html><head><title>History</title>$STYLE</head>
<body><div class='page'>
  <h1>ORDER HISTORY</h1>

  <div class='card'>
    <div class='small'>Logged in as: <span class='pill' id='who'>$user</span></div>
    <div id='content' class='small' style='margin-top:12px'>Loading...</div>

    <div class='btnrow' style='margin-top:14px'>
      <button class='secondary' onclick="window.location.href='/builder'">Back to Menu</button>
    </div>
  </div>

<script>
async function loadHistory(){
  const el = document.getElementById('content');
  try{
    const res = await fetch('/api/history', {credentials:'include'});
    const ct = res.headers.get("content-type") || "";
    if(!ct.includes("application/json")){
      el.innerText = "History failed (server returned non-JSON). Please login again.";
      return;
    }
    const data = await res.json();
    if(!res.ok || !data.ok){
      el.innerText = "Error: " + (data.error || ("HTTP " + res.status));
      return;
    }

    const orders = data.orders || [];
    if(orders.length === 0){
      el.innerHTML = "<p class='small'>No orders yet.</p>";
      return;
    }

    let html = '<table class="table"><tr><th>Drink</th><th>Qty</th><th>Calories</th><th>Time</th></tr>';
    orders.slice().reverse().forEach(o=>{
      html += `<tr>
        <td>${o.drinkName || ''}</td>
        <td>${o.quantity || 1}</td>
        <td>${o.calories || 0}</td>
        <td>${o.ts || ''}</td>
      </tr>`;
    });
    html += '</table>';
    el.innerHTML = html;
  }catch(e){
    el.innerText = "History error: " + e;
  }
}
loadHistory();
</script>

</div></body></html>
""")

    return HTMLResponse(tpl.safe_substitute(STYLE=STYLE, user=user))


@router.get("/drink-links", response_class=HTMLResponse)
def drink_links_page(request: Request):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    ensure_drinks_file()
    drinks = load_drinks()

    rows = "".join([
        f"<tr><td>{d.get('name','')}</td>"
        f"<td><span class='pill'>{d.get('calories',0)} cal</span></td>"
        f"<td><a href='/drink/{d.get('id')}'><b>/drink/{d.get('id')}</b></a></td></tr>"
        for d in drinks
    ])

    return HTMLResponse(f"""
    <html><head><title>Drink Links</title>{STYLE}</head>
    <body><div class='page'>
      <h1>DRINK LINKS</h1>
      <div class='card'>
        <div class='small'>Copy these links into Canva using your deployed domain.</div>
        <table class='table'>
          <tr><th>Drink</th><th>Calories</th><th>Link</th></tr>
          {rows}
        </table>
        <div class='btnrow' style='margin-top:14px'>
          <button class='secondary' onclick="window.location.href='/builder'">Back to Menu</button>
        </div>
      </div>
    </div></body></html>
    """)


@router.get("/recommendations", response_class=HTMLResponse)
def recommendations_page(request: Request):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    top = _top_drinks_for_user(user, limit=3)
    top_html = "<p class='small'>No orders yet.</p>" if not top else "<ul>" + "".join(
        [f"<li style='color:#f5e6d3'>{n}</li>" for n in top]
    ) + "</ul>"

    recs = recommend_for_user(user, k=5)
    if not recs:
        rec_html = "<p class='small'>No recommendations yet.</p>"
    else:
        rec_html = "<ul>" + "".join([
            f"<li style='color:#f5e6d3'><b>{d.get('name')}</b> "
            f"<span class='pill' style='margin-left:8px'>{d.get('calories',0)} cal</span></li>"
            for d in recs
        ]) + "</ul>"

    return HTMLResponse(f"""
    <html><head><title>Recommendations</title>{STYLE}</head>
    <body><div class='page'>
      <h1>RECOMMENDATIONS</h1>
      <div class='grid cards'>
        <div class='card'>
          <h2>NEW DRINKS FOR YOU</h2>
          <div class='small'>Based on similar users + popularity.</div>
          {rec_html}
        </div>
        <div class='card'>
          <h2>YOUR TOP DRINKS</h2>
          <div class='small'>What you order the most.</div>
          {top_html}
        </div>
      </div>
      <div class='btnrow' style='margin-top:14px'>
        <button class='secondary' onclick="window.location.href='/builder'">Back to Menu</button>
      </div>
    </div></body></html>
    """)
