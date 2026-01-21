from collections import Counter
from string import Template

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import CANVA_URL
from app.core.auth import current_user
from app.core.storage import ensure_drinks_file, load_drinks, load_orders
from app.ml.recommender import recommend_for_user

router = APIRouter()

# =====================
# STYLES
# =====================
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
  color:#f5e6d3;
}
a{color:#f5e6d3}
.page{max-width:1100px;margin:0 auto;padding:40px 20px 60px}
h1{
  font-size:42px;
  letter-spacing:3px;
  text-align:center;
  margin:0 0 10px;
}
.grid{display:grid;gap:16px}
.cards{grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}
.card{
  background:rgba(0,0,0,.55);
  border:1px solid rgba(245,230,211,.25);
  border-radius:18px;
  padding:18px;
}
.card h2{margin:0 0 10px;letter-spacing:2px}
.btnrow{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
button,.primary,.secondary{
  border-radius:14px;
  padding:12px 14px;
  font-family:inherit;
  font-weight:700;
  cursor:pointer;
}
.primary{background:#f5e6d3;color:#1f130d;border:none}
.secondary{background:rgba(0,0,0,.4);color:#f5e6d3;border:1px solid rgba(245,230,211,.3)}
.small{color:rgba(245,230,211,.85)}
hr{border:0;border-top:1px solid rgba(245,230,211,.18);margin:14px 0}
.table{width:100%;border-collapse:collapse;margin-top:10px}
.table th,.table td{border-bottom:1px solid rgba(245,230,211,.18);padding:10px;color:#f5e6d3}
.pill{display:inline-block;padding:6px 10px;border-radius:999px;border:1px solid rgba(245,230,211,.3)}
.qty-pill{min-width:44px;text-align:center}
</style>
"""

# =====================
# HELPERS
# =====================
def _require_user(request: Request):
    return current_user(request)

def _username(request: Request):
    u = current_user(request)
    if not u:
        return None
    if isinstance(u, dict):
        return u.get("username") or u.get("user")
    return u

def _find_drink(drink_id: str):
    ensure_drinks_file()
    for d in load_drinks():
        if d.get("id") == drink_id:
            return d
    return None

def _top_drinks(username: str, limit=3):
    orders = load_orders()
    c = Counter()
    for o in orders:
        if o.get("username") == username:
            c[o.get("drinkName")] += int(o.get("quantity", 1))
    return [n for n,_ in c.most_common(limit)]

# =====================
# ROUTES
# =====================
@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return RedirectResponse("/dashboard" if _require_user(request) else "/login", status_code=302)

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = _require_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    username = _username(request)

    return HTMLResponse(f"""
    <html><head><title>Dashboard</title>{STYLE}</head>
    <body><div class="page">
      <h1>DASHBOARD</h1>
      <div class="grid cards">
        <div class="card">
          <h2>MENU</h2>
          <div class="small">Browse drinks and order</div>
          <div class="btnrow">
            <button class="primary" onclick="location.href='/builder'">Open Menu</button>
          </div>
        </div>

        <div class="card">
          <h2>HISTORY</h2>
          <div class="small">Your past orders</div>
          <div class="btnrow">
            <button class="secondary" onclick="location.href='/history'">View</button>
          </div>
        </div>

        <div class="card">
          <h2>RECOMMEND</h2>
          <div class="small">Personalized drinks</div>
          <div class="btnrow">
            <button class="secondary" onclick="location.href='/recommendations'">See</button>
          </div>
        </div>

        <div class="card">
          <h2>CANVA</h2>
          <div class="btnrow">
            <a class="secondary" href="{CANVA_URL}" target="_blank">Open Canva</a>
          </div>
        </div>
      </div>

      <div class="btnrow" style="margin-top:20px">
        <button class="secondary" onclick="location.href='/logout'">Logout</button>
      </div>
    </div></body></html>
    """)

@router.get("/menu")
def menu_alias():
    return RedirectResponse("/builder", status_code=302)

@router.get("/builder", response_class=HTMLResponse)
def builder(request: Request):
    if not _require_user(request):
        return RedirectResponse("/login", status_code=302)

    ensure_drinks_file()

    return HTMLResponse(f"""
<html><head><title>Menu</title>{STYLE}</head>
<body><div class="page">
<h1>SMART BARTENDER</h1>

<div class="card">
  <h2>MENU</h2>
  <div id="menu" class="grid cards"></div>

  <hr/>
  <h2>CART</h2>
  <div id="cart" class="small">No items yet.</div>

  <div class="btnrow">
    <button class="primary" onclick="checkout()">Checkout</button>
    <button class="secondary" onclick="location.href='/dashboard'">Back</button>
  </div>

  <div id="status" class="small"></div>
</div>

<script>
let drinks = [];
let cart = {};

function renderMenu(){
  const el = document.getElementById('menu');
  el.innerHTML = '';
  drinks.forEach(d=>{
    el.innerHTML += `
      <div class="card">
        <h2>${{d.name}}</h2>
        <div class="small">Calories: <span class="pill">${{d.calories||0}}</span></div>
        <div class="btnrow">
          <button class="secondary" onclick="add('${{d.id}}','${{d.name}}',${{d.calories||0}})">Add</button>
          <button class="secondary" onclick="remove('${{d.id}}')">Remove</button>
        </div>
      </div>`;
  });
}

function renderCart(){
  const el = document.getElementById('cart');
  const keys = Object.keys(cart);
  if(!keys.length){ el.innerText='No items yet.'; return; }
  let html='<table class="table"><tr><th>Drink</th><th>Qty</th></tr>';
  keys.forEach(k=>{
    html+=`<tr><td>${{cart[k].drinkName}}</td><td>${{cart[k].quantity}}</td></tr>`;
  });
  html+='</table>';
  el.innerHTML=html;
}

function add(id,name,cal){
  if(!cart[id]) cart[id]={drinkId:id,drinkName:name,quantity:0,calories:cal};
  cart[id].quantity++;
  renderCart();
}

function remove(id){
  if(!cart[id]) return;
  cart[id].quantity--;
  if(cart[id].quantity<=0) delete cart[id];
  renderCart();
}

async function checkout(){
  const status=document.getElementById('status');
  status.innerText='Checking out...';
  const items=Object.values(cart);
  if(!items.length){status.innerText='Cart empty';return;}

  const res=await fetch('/checkout',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({items})
  });

  const ct=res.headers.get('content-type')||'';
  if(!ct.includes('application/json')){
    status.innerText='Session expired. Please login again.';
    return;
  }

  const data=await res.json();
  if(!res.ok || !data.ok){
    status.innerText='Error: '+(data.error||res.status);
    return;
  }

  cart={};
  renderCart();
  status.innerText='Saved successfully!';
}

(async()=>{
  const r=await fetch('/api/drinks');
  drinks=await r.json();
  renderMenu();
})();
</script>
</div></body></html>
""")

@router.get("/history", response_class=HTMLResponse)
def history(request: Request):
    user = _username(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    orders = [o for o in load_orders() if o.get("username")==user]
    rows = "<p class='small'>No orders yet.</p>" if not orders else \
        "<table class='table'><tr><th>Drink</th><th>Qty</th><th>Time</th></tr>" + \
        "".join([f"<tr><td>{o['drinkName']}</td><td>{o['quantity']}</td><td>{o['ts']}</td></tr>" for o in orders[::-1]]) + "</table>"

    return HTMLResponse(f"<html><head><title>History</title>{STYLE}</head><body><div class='page'><h1>HISTORY</h1><div class='card'>{rows}<div class='btnrow'><button class='secondary' onclick=\"location.href='/dashboard'\">Back</button></div></div></div></body></html>")

@router.get("/recommendations", response_class=HTMLResponse)
def recommendations(request: Request):
    user=_username(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    top=_top_drinks(user)
    recs=recommend_for_user(user)

    return HTMLResponse(f"<html><head><title>Recommendations</title>{STYLE}</head><body><div class='page'><h1>RECOMMENDATIONS</h1><div class='grid cards'><div class='card'><h2>Top Drinks</h2>{''.join(f'<div>{x}</div>' for x in top) or '<p class=small>No data</p>'}</div><div class='card'><h2>Suggested</h2>{''.join(f'<div>{d['name']}</div>' for d in recs) or '<p class=small>No data</p>'}</div></div><div class='btnrow'><button class='secondary' onclick=\"location.href='/dashboard'\">Back</button></div></div></body></html>")
