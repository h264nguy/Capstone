from collections import Counter
from string import Template

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import CANVA_URL
from app.core.auth import current_user
from app.core.storage import ensure_drinks_file, load_drinks, load_orders
from app.ml.recommender import recommend_for_user

router = APIRouter()

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
.card h2{margin:0 0 10px;color:#f5e6d3;letter-spacing:2px}
.btnrow{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
button,.primary,.secondary{
  appearance:none;border:0;cursor:pointer;
  padding:12px 14px;border-radius:14px;
  font-family:inherit;
  font-weight:700;
  letter-spacing:1px;
}
.primary{background:#f5e6d3;color:#1f130d}
.secondary{background:rgba(0,0,0,.35);color:#f5e6d3;border:1px solid rgba(245,230,211,.25)}
.small{color:rgba(245,230,211,.85)}
hr{border:0;border-top:1px solid rgba(245,230,211,.18);margin:14px 0}
.table{width:100%;border-collapse:collapse;margin-top:10px}
.table th,.table td{border-bottom:1px solid rgba(245,230,211,.18);padding:10px 8px;color:#f5e6d3;text-align:left}
.table th{color:rgba(245,230,211,.92)}
.pill{display:inline-block;padding:6px 10px;border-radius:999px;background:rgba(245,230,211,.12);border:1px solid rgba(245,230,211,.18);color:#f5e6d3;font-size:12px}
.qty-pill{min-width:44px;text-align:center;display:inline-flex;align-items:center;justify-content:center}
</style>
"""

def _require_user(request: Request):
    user = current_user(request)
    return user if user else None

def _top_drinks_for_user(username: str, limit: int = 3):
    orders = load_orders()
    c = Counter()
    for o in orders:
        if o.get("username") == username:
            c[o.get("drinkName")] += int(o.get("quantity", 1) or 1)
    return [name for name, _ in c.most_common(limit)]

def _find_drink(drink_id: str):
    ensure_drinks_file()
    for d in load_drinks():
        if d.get("id") == drink_id:
            return d
    return None

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return RedirectResponse("/dashboard" if current_user(request) else "/login", status_code=302)

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    username = request.session.get("user") or request.session.get("username") or user

    tpl = Template("""
    <html><head><title>Dashboard</title>$STYLE</head>
    <body><div class='page'>
      <h1>DASHBOARD</h1>
      <div style='text-align:center;'>
        <div class='pill'>Welcome, $USERNAME</div>
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
          <div class='small'>Get new drink suggestions based on similar users.</div>
          <div class='btnrow'>
            <button class='secondary' onclick="window.location.href='/recommendations'">See Recommendations</button>
          </div>
        </div>

        <div class='card'>
          <h2>CANVA</h2>
          <div class='small'>Open your Canva page in a new tab.</div>
          <div class='btnrow'>
            <a class='secondary' href='$CANVA' target='_blank' rel='noopener'>Open Canva</a>
          </div>
        </div>

        <!-- (You asked earlier to remove the MENU card UI) -->
      </div>

      <div class='btnrow' style='margin-top:14px'>
        <button class='secondary' onclick="window.location.href='/logout'">Logout</button>
      </div>
    </div></body></html>
    """)

    return HTMLResponse(tpl.safe_substitute(
        STYLE=STYLE,
        USERNAME=str(username),
        CANVA=CANVA_URL
    ))

@router.get("/menu", response_class=HTMLResponse)
def menu_alias(request: Request):
    return RedirectResponse("/builder", status_code=302)

@router.get("/builder", response_class=HTMLResponse)
def builder(request: Request):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    ensure_drinks_file()

    # IMPORTANT: This MUST NOT be an f-string because JS uses { }
    html = Template(r"""
    <html><head><title>Builder</title>$STYLE</head>
    <body><div class='page'>
      <h1>SMART BARTENDER</h1>
      <div class='card'>
        <h2>MENU</h2>
        <div class='small'>Pick drinks and quantities. Then checkout to save order history (and optionally send to ESP).</div>
        <div id='menu' class='grid cards' style='margin-top:14px'></div>

        <hr/>
        <h2>CART</h2>
        <div id='cart' class='small'>No items yet.</div>
        <div class='btnrow'>
          <button class='primary' onclick='checkout()'>Checkout</button>
          <button class='secondary' onclick="window.location.href='/dashboard'">Back</button>
        </div>
        <div id='status' class='small' style='margin-top:10px'></div>
      </div>

<script>
let drinks = [];
let cart = {};

function renderMenu(){
  const el = document.getElementById('menu');
  el.innerHTML = '';
  drinks.forEach(d => {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <h2>${d.name}</h2>
      <div class='small'>Calories: <span class='pill'>${d.calories || 0} cal</span></div>
      <div class='btnrow' style='margin-top:12px'>
        <a class='secondary' style='text-decoration:none;display:inline-block' href="/drink/${d.id}">Open</a>
        <button class='secondary' onclick="addToCart('${d.id}','${d.name}',${d.calories||0})">Add</button>
        <button class='secondary' onclick="removeFromCart('${d.id}')">Remove</button>
      </div>
    `;
    el.appendChild(card);
  });
}

function renderCart(){
  const el = document.getElementById('cart');
  const keys = Object.keys(cart);
  if(keys.length===0){ el.innerHTML='No items yet.'; return; }
  let html = '<table class="table"><tr><th>Drink</th><th>Qty</th><th>Calories</th></tr>';
  keys.forEach(k=>{
    const it = cart[k];
    html += `<tr><td>${it.drinkName}</td><td>${it.quantity}</td><td>${it.calories}</td></tr>`;
  });
  html += '</table>';
  el.innerHTML = html;
}

function addToCart(id,name,cal){
  if(!cart[id]) cart[id] = {drinkId:id, drinkName:name, quantity:0, calories:cal};
  cart[id].quantity += 1;
  renderCart();
}

function removeFromCart(id){
  if(!cart[id]) return;
  cart[id].quantity -= 1;
  if(cart[id].quantity <= 0) delete cart[id];
  renderCart();
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
    status.innerText = "Checkout failed (server returned non-JSON). Please login again.";
    return;
  }

  const data = await res.json();

  if (!res.ok || !data.ok) {
    status.innerText = "Error: " + (data.error || ("HTTP " + res.status));
    return;
  }

  cart = {};
  renderCart();
  status.innerText = data.esp ? "Saved + sent to ESP! ✅" : "Saved! ✅ (ESP not reachable)";
}

(async function init(){
  const r = await fetch('/api/drinks');
  drinks = await r.json();
  renderMenu();
  renderCart();
})();
</script>

    </div></body></html>
    """).safe_substitute(STYLE=STYLE)

    return HTMLResponse(html)

@router.get("/drink/{drink_id}", response_class=HTMLResponse)
def drink_page(request: Request, drink_id: str):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    d = _find_drink(drink_id)
    if not d:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    name = d.get("name", drink_id)
    cal = int(d.get("calories", 0) or 0)

    tpl = Template(r"""
    <html><head><title>$NAME</title>$STYLE</head>
    <body><div class='page'>
      <h1>$NAME_UPPER</h1>
      <div class='grid cards'>
        <div class='card'>
          <h2>ORDER THIS DRINK</h2>
          <div class='small'>Calories: <span class='pill'>$CAL cal</span></div>
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
            <button class='secondary' onclick="window.location.href='/dashboard'">Dashboard</button>
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

  const items = [{drinkId: "$DRINK_ID", drinkName: "$NAME", quantity: quantity, calories: $CAL}];

  const res = await fetch('/checkout', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({items})
  });

  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) {
    status.innerText = "Checkout failed (server returned non-JSON). Please login again.";
    return;
  }

  const data = await res.json();

  if (!res.ok || !data.ok) {
    status.innerText = "Error: " + (data.error || ("HTTP " + res.status));
    return;
  }

  status.innerText = data.esp ? "Saved + sent to ESP! ✅" : "Saved! ✅ (ESP not reachable)";
}

setQty();
</script>

    </div></body></html>
    """)

    return HTMLResponse(tpl.safe_substitute(
        STYLE=STYLE,
        NAME=name,
        NAME_UPPER=name.upper(),
        DRINK_ID=drink_id,
        CAL=str(cal)
    ))

@router.get("/history", response_class=HTMLResponse)
def history(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    # IMPORTANT: normalize username (matches checkout)
    username = (
        request.session.get("username")
        or request.session.get("user")
        or user
    )

    orders = [o for o in load_orders() if o.get("username") == username]

    if not orders:
        rows = "<p class='small'>No orders yet.</p>"
    else:
        rows = "<table class='table'><tr><th>Drink</th><th>Qty</th><th>Calories</th><th>Time</th></tr>"
        for o in reversed(orders):
            rows += (
                f"<tr>"
                f"<td>{o.get('drinkName','')}</td>"
                f"<td>{o.get('quantity',1)}</td>"
                f"<td>{o.get('calories',0)}</td>"
                f"<td>{o.get('ts','')}</td>"
                f"</tr>"
            )
        rows += "</table>"

    return HTMLResponse(f"""
    <html><head><title>History</title>{STYLE}</head>
    <body><div class='page'>
      <h1>ORDER HISTORY</h1>
      <div class='card'>
        {rows}
        <div class='btnrow' style='margin-top:14px'>
          <button class='secondary' onclick="window.location.href='/builder'">Back to Menu</button>
          <button class='secondary' onclick="window.location.href='/dashboard'">Dashboard</button>
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
    top_html = "<p class='small'>No orders yet.</p>" if not top else "<ul>" + "".join([f"<li style='color:#f5e6d3'>{n}</li>" for n in top]) + "</ul>"

    recs = recommend_for_user(user, k=5)
    if not recs:
        rec_html = "<p class='small'>No recommendations yet.</p>"
    else:
        rec_html = "<ul>" + "".join([
            f"<li style='color:#f5e6d3'><b>{d.get('name')}</b> <span class='pill' style='margin-left:8px'>{d.get('calories',0)} cal</span></li>"
            for d in recs
        ]) + "</ul>"

    return HTMLResponse(f"""
    <html><head><title>Recommendations</title>{STYLE}</head>
    <body><div class='page'>
      <h1>RECOMMENDATIONS</h1>
      <div class='grid cards'>
        <div class='card'>
          <h2>NEW DRINKS FOR YOU</h2>
          <div class='small'>Based on similar users + popularity (and excluding drinks you've already tried).</div>
          {rec_html}
        </div>
        <div class='card'>
          <h2>YOUR TOP DRINKS</h2>
          <div class='small'>What you order the most.</div>
          {top_html}
        </div>
      </div>

      <div class='btnrow' style='margin-top:14px'>
        <button class='secondary' onclick="window.location.href='/builder'">Back to Builder</button>
        <button class='secondary' onclick="window.location.href='/dashboard'">Dashboard</button>
      </div>
    </div></body></html>
    """)
