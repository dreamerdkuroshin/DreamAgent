"""
backend/builder/generators/static_store.py
Generates a beautiful, self-contained single-file ecommerce store
using the real user preferences from the builder form.
"""

DESIGN_PALETTES = {
    "modern": {
        "bg": "#0f0f13",
        "surface": "#1a1a24",
        "accent": "#7c6aff",
        "accent2": "#ff6a9b",
        "text": "#e8e8f0",
        "muted": "#8888aa",
    },
    "minimal": {
        "bg": "#f8f9fa",
        "surface": "#ffffff",
        "accent": "#0066ff",
        "accent2": "#00cc88",
        "text": "#1a1a1a",
        "muted": "#666666",
    },
    "premium": {
        "bg": "#0a0805",
        "surface": "#1a1308",
        "accent": "#c9a84c",
        "accent2": "#e8d5a3",
        "text": "#f5f0e8",
        "muted": "#a09070",
    },
    "dark": {
        "bg": "#070910",
        "surface": "#10121a",
        "accent": "#00ebff",
        "accent2": "#8b5cf6",
        "text": "#e2e8f0",
        "muted": "#6b7280",
    },
    "colorful": {
        "bg": "#fff8f0",
        "surface": "#ffffff",
        "accent": "#ff4757",
        "accent2": "#2ed573",
        "text": "#2d2d2d",
        "muted": "#777777",
    },
    # legacy aliases
    "luxury": {
        "bg": "#0a0805",
        "surface": "#1a1308",
        "accent": "#c9a84c",
        "accent2": "#e8d5a3",
        "text": "#f5f0e8",
        "muted": "#a09070",
    },
    "simple": {
        "bg": "#f8f9fa",
        "surface": "#ffffff",
        "accent": "#0066ff",
        "accent2": "#00cc88",
        "text": "#1a1a1a",
        "muted": "#666666",
    },
}

FOOD_EMOJI = ["🍕", "🍔", "🥗", "🍜", "🌮", "🍣", "🥪", "🍰", "☕", "🧁"]


def _build_products_js(products: list) -> str:
    """Build a JS array from user's product list."""
    items = []
    for i, prod in enumerate(products):
        name = (prod.get("name") or f"Item {i+1}").replace("'", "\\'")
        desc = (prod.get("description") or "").replace("'", "\\'")
        price = str(prod.get("price") or "0").replace("'", "")
        img = prod.get("image") or ""
        if img.startswith("http"):
            img_html = f"<img src=\\'{img}\\' style=\\'width:100%;height:100%;object-fit:cover;\\' />"
        else:
            emoji = img if img else FOOD_EMOJI[i % len(FOOD_EMOJI)]
            img_html = f"<span style=\\'font-size:3rem;\\'>{emoji}</span>"
        badge = "NEW" if i == 0 else ("HOT" if i == 1 else "")
        badge_str = f"'{badge}'" if badge else "null"
        items.append(
            f"  {{id:{i+1},imgHtml:'{img_html}',name:'{name}',desc:'{desc}',price:'{price}',badge:{badge_str}}}"
        )
    return "[\n" + ",\n".join(items) + "\n]"


def _build_fallback_products_js() -> str:
    return """[
  {id:1,imgHtml:'<span style="font-size:3rem;">🛍️</span>',name:'Premium Item 1',desc:'Quality product, handpicked for you.',price:'99',badge:'BESTSELLER'},
  {id:2,imgHtml:'<span style="font-size:3rem;">✨</span>',name:'Exclusive Item 2',desc:'Unique and high-quality.',price:'149',badge:'NEW'},
  {id:3,imgHtml:'<span style="font-size:3rem;">🎯</span>',name:'Popular Item 3',desc:'Best value for money.',price:'59',badge:'HOT'}
]"""


def _build_socials_html(socials: list) -> str:
    icons = {"youtube": "📺", "instagram": "📷", "twitter": "🐦", "facebook": "📘"}
    parts = []
    for s in socials:
        platform = s.get("platform", "")
        url = s.get("url", "#") or "#"
        icon = icons.get(platform, "🔗")
        parts.append(
            f'<a href="{url}" target="_blank" style="color:var(--muted);text-decoration:none;" '
            f'onmouseover="this.style.color=\'var(--accent)\'" onmouseout="this.style.color=\'var(--muted)\'">'
            f"{icon} {platform.title()}</a>"
        )
    return " &nbsp;|&nbsp; ".join(parts)


def _build_contact_html(contact: dict) -> str:
    parts = []
    if contact.get("address"):
        parts.append(f'📍 {contact["address"]}')
    if contact.get("phone"):
        parts.append(f'📞 {contact["phone"]}')
    if contact.get("email"):
        parts.append(f'✉️ <a href="mailto:{contact["email"]}" style="color:var(--accent)">{contact["email"]}</a>')
    return " &nbsp;&bull;&nbsp; ".join(parts)


def generate(prefs: dict) -> dict:
    """Returns dict of {filename: content} using real user preferences."""
    palette_key = prefs.get("design", "modern") or "modern"
    p = DESIGN_PALETTES.get(palette_key, DESIGN_PALETTES["modern"])

    # Features
    _features = prefs.get("features", {})
    if isinstance(_features, list):
        fl = [str(f).lower() for f in _features]
        has_auth = "auth" in fl
        has_payment = "payment" in fl
    else:
        has_auth = bool(_features.get("auth", False))
        has_payment = bool(_features.get("payment", False))

    # Real user content from the form
    site_name = (prefs.get("name") or "My Store").strip()
    purpose = (prefs.get("purpose") or f"Welcome to {site_name}. Discover our collection.").strip()
    raw_products = prefs.get("products") or []
    contact = prefs.get("contact") or {}
    socials = prefs.get("socials") or []
    footer_text = (prefs.get("footer") or f"© 2025 {site_name}. All rights reserved.").strip()

    # Build dynamic JS product array
    has_real_products = any(p.get("name") for p in raw_products)
    products_js = _build_products_js(raw_products) if has_real_products else _build_fallback_products_js()

    socials_html = _build_socials_html(socials)
    contact_html = _build_contact_html(contact)

    # Auth modal snippet
    auth_modal = (
        '<div class="modal-overlay" id="auth-modal">'
        '<div class="modal"><button class="modal-close" onclick="closeModal()">×</button>'
        '<h2>Welcome back 👋</h2>'
        '<div class="form-group"><label>Email</label><input type="email" placeholder="you@example.com" /></div>'
        '<div class="form-group"><label>Password</label><input type="password" placeholder="••••••••" /></div>'
        '<button class="modal-btn">Sign In</button></div></div>'
    ) if has_auth else ""

    auth_js = (
        'function openModal(){document.getElementById("auth-modal").classList.add("open");}'
        'function closeModal(){document.getElementById("auth-modal").classList.remove("open");}'
    ) if has_auth else ""

    nav_btn = (
        '<button class="nav-cta" onclick="openModal()">Sign In</button>'
        if has_auth else
        '<button class="nav-cta" onclick="scrollToProducts()">Order Now</button>'
    )

    contact_block = f'<div class="contact-info">{contact_html}</div>' if contact_html else ""
    socials_block = f'<div class="social-links">{socials_html}</div>' if socials_html else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{site_name}</title>
  <meta name="description" content="{purpose}" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;900&display=swap" rel="stylesheet" />
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    :root{{
      --bg:{p['bg']};--surface:{p['surface']};
      --accent:{p['accent']};--accent2:{p['accent2']};
      --text:{p['text']};--muted:{p['muted']};
      --radius:16px;--transition:0.25s cubic-bezier(0.4,0,0.2,1)
    }}
    body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}}
    nav{{position:sticky;top:0;z-index:100;display:flex;align-items:center;
      justify-content:space-between;padding:1rem 2rem;background:var(--surface);
      backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,0.05);
      box-shadow:0 4px 30px rgba(0,0,0,0.3)}}
    .nav-brand{{font-size:1.4rem;font-weight:900;letter-spacing:-1px;
      background:linear-gradient(135deg,var(--accent),var(--accent2));
      -webkit-background-clip:text;-webkit-text-fill-color:transparent}}
    .nav-links{{display:flex;gap:2rem;list-style:none}}
    .nav-links a{{text-decoration:none;color:var(--muted);font-size:.9rem;font-weight:500;
      transition:color var(--transition)}}
    .nav-links a:hover{{color:var(--text)}}
    .nav-cta{{padding:.55rem 1.4rem;border-radius:100px;background:var(--accent);
      color:#fff;border:none;cursor:pointer;font-weight:600;font-size:.875rem;
      transition:opacity var(--transition)}}
    .nav-cta:hover{{opacity:.85}}
    .hero{{text-align:center;padding:6rem 2rem 4rem;
      background:radial-gradient(ellipse 80% 60% at 50% -20%,
      color-mix(in srgb,var(--accent) 20%,transparent),transparent)}}
    .hero-badge{{display:inline-block;padding:.3rem 1rem;border-radius:100px;
      border:1px solid var(--accent);color:var(--accent);font-size:.78rem;
      font-weight:600;letter-spacing:.5px;margin-bottom:1.5rem}}
    .hero h1{{font-size:clamp(2.5rem,7vw,5rem);font-weight:900;line-height:1.05;
      letter-spacing:-2px;margin-bottom:1.5rem}}
    .hero h1 span{{background:linear-gradient(135deg,var(--accent),var(--accent2));
      -webkit-background-clip:text;-webkit-text-fill-color:transparent}}
    .hero p{{max-width:600px;margin:0 auto 2.5rem;color:var(--muted);
      font-size:1.1rem;line-height:1.7}}
    .hero-btns{{display:flex;gap:1rem;justify-content:center;flex-wrap:wrap}}
    .btn-primary{{padding:.9rem 2.2rem;border-radius:100px;
      background:linear-gradient(135deg,var(--accent),var(--accent2));
      color:#fff;border:none;cursor:pointer;font-weight:700;font-size:1rem;
      transition:transform var(--transition),box-shadow var(--transition);
      box-shadow:0 4px 30px color-mix(in srgb,var(--accent) 40%,transparent)}}
    .btn-primary:hover{{transform:translateY(-2px);
      box-shadow:0 8px 40px color-mix(in srgb,var(--accent) 60%,transparent)}}
    .btn-secondary{{padding:.9rem 2.2rem;border-radius:100px;border:1px solid var(--muted);
      color:var(--text);background:transparent;cursor:pointer;font-weight:600;font-size:1rem;
      transition:border-color var(--transition)}}
    .btn-secondary:hover{{border-color:var(--text)}}
    .products{{padding:4rem 2rem;max-width:1200px;margin:0 auto}}
    .section-title{{text-align:center;margin-bottom:3rem}}
    .section-title h2{{font-size:2.2rem;font-weight:800;letter-spacing:-1px}}
    .section-title p{{color:var(--muted);margin-top:.5rem}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1.5rem}}
    .card{{background:var(--surface);border-radius:var(--radius);overflow:hidden;
      border:1px solid rgba(255,255,255,0.05);
      transition:transform var(--transition),box-shadow var(--transition);cursor:pointer}}
    .card:hover{{transform:translateY(-6px);box-shadow:0 20px 60px rgba(0,0,0,.3)}}
    .card-img{{height:220px;background:linear-gradient(135deg,var(--accent),var(--accent2));
      display:flex;align-items:center;justify-content:center;
      position:relative;overflow:hidden}}
    .badge{{position:absolute;top:12px;right:12px;z-index:1;background:var(--accent2);
      color:#fff;font-size:.7rem;font-weight:700;padding:.2rem .6rem;border-radius:100px}}
    .card-body{{padding:1.25rem}}
    .card-title{{font-weight:700;margin-bottom:.3rem}}
    .card-desc{{color:var(--muted);font-size:.85rem;margin-bottom:1rem;line-height:1.5}}
    .card-footer{{display:flex;align-items:center;justify-content:space-between}}
    .price{{font-weight:800;font-size:1.25rem;
      background:linear-gradient(135deg,var(--accent),var(--accent2));
      -webkit-background-clip:text;-webkit-text-fill-color:transparent}}
    .add-btn{{padding:.5rem 1.2rem;border-radius:100px;background:var(--accent);
      color:#fff;border:none;font-size:.85rem;font-weight:600;cursor:pointer;
      transition:opacity var(--transition),transform var(--transition)}}
    .add-btn:hover{{opacity:.85;transform:scale(1.05)}}
    .add-btn.added{{background:var(--accent2)}}
    #cart-toast{{position:fixed;bottom:2rem;right:2rem;background:var(--surface);
      border:1px solid var(--accent);border-radius:var(--radius);padding:1rem 1.5rem;
      box-shadow:0 8px 40px rgba(0,0,0,.4);transform:translateY(120px);opacity:0;
      transition:all var(--transition);z-index:999;display:flex;align-items:center;gap:.75rem}}
    #cart-toast.show{{transform:translateY(0);opacity:1}}
    footer{{text-align:center;padding:3rem 2rem;color:var(--muted);font-size:.85rem;
      border-top:1px solid rgba(255,255,255,.05)}}
    footer span{{color:var(--accent)}}
    .social-links{{margin-top:.75rem;font-size:.9rem}}
    .contact-info{{margin-top:.5rem;font-size:.8rem}}
    .modal-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);
      backdrop-filter:blur(8px);z-index:200;align-items:center;justify-content:center}}
    .modal-overlay.open{{display:flex}}
    .modal{{background:var(--surface);border-radius:var(--radius);padding:2.5rem;
      width:min(420px,90vw);border:1px solid rgba(255,255,255,.08);
      box-shadow:0 30px 80px rgba(0,0,0,.5)}}
    .modal h2{{font-size:1.5rem;font-weight:800;margin-bottom:1.5rem}}
    .form-group{{margin-bottom:1rem}}
    .form-group label{{display:block;font-size:.85rem;color:var(--muted);
      margin-bottom:.4rem;font-weight:500}}
    .form-group input{{width:100%;padding:.75rem 1rem;border-radius:10px;
      background:var(--bg);border:1px solid rgba(255,255,255,.08);color:var(--text);
      font-size:.95rem;outline:none;transition:border-color var(--transition)}}
    .form-group input:focus{{border-color:var(--accent)}}
    .modal-btn{{width:100%;padding:.85rem;margin-top:.5rem;border-radius:10px;
      background:var(--accent);color:#fff;border:none;font-size:1rem;
      font-weight:700;cursor:pointer;transition:opacity var(--transition)}}
    .modal-btn:hover{{opacity:.85}}
    .modal-close{{float:right;background:none;border:none;color:var(--muted);
      cursor:pointer;font-size:1.5rem;line-height:1}}
    @media(max-width:640px){{.nav-links{{display:none}}}}
  </style>
</head>
<body>
  <nav>
    <div class="nav-brand">✦ {site_name}</div>
    <ul class="nav-links">
      <li><a href="#products">Menu</a></li>
      <li><a href="#about">About</a></li>
      <li><a href="#contact">Contact</a></li>
    </ul>
    <div style="display:flex;gap:.75rem;align-items:center;">
      <span id="cart-count" style="color:var(--accent);font-weight:700;font-size:.9rem;">🛒 0</span>
      {nav_btn}
    </div>
  </nav>

  <section class="hero">
    <div class="hero-badge">✦ {site_name.upper()}</div>
    <h1>Welcome to <span>{site_name}</span></h1>
    <p>{purpose}</p>
    <div class="hero-btns">
      <button class="btn-primary" onclick="scrollToProducts()">See Our Menu →</button>
      <button class="btn-secondary" onclick="document.getElementById('contact').scrollIntoView({{behavior:'smooth'}})">Contact Us</button>
    </div>
  </section>

  <section class="products" id="products">
    <div class="section-title">
      <h2>Our Menu</h2>
      <p>Fresh, made with love, delivered to you</p>
    </div>
    <div class="grid" id="product-grid"></div>
  </section>

  <div id="cart-toast">
    <span style="font-size:1.4rem;">🛒</span>
    <div>
      <div style="font-weight:700;font-size:.95rem;">Added to order!</div>
      <div style="color:var(--muted);font-size:.8rem;">Keep browsing or checkout</div>
    </div>
  </div>

  {auth_modal}

  <footer id="contact">
    <div>{footer_text}</div>
    {contact_block}
    {socials_block}
    <div style="margin-top:.75rem;">Built with <span>❤ DreamAgent</span></div>
  </footer>

  <script>
    const PRODUCTS = {products_js};
    let cart = 0;

    function renderProducts() {{
      const grid = document.getElementById('product-grid');
      grid.innerHTML = PRODUCTS.map(p => `
        <div class="card" onclick="addToCart(this, ${{p.id}})">
          <div class="card-img">
            ${{p.badge ? `<div class="badge">${{p.badge}}</div>` : ''}}
            ${{p.imgHtml}}
          </div>
          <div class="card-body">
            <div class="card-title">${{p.name}}</div>
            <div class="card-desc">${{p.desc}}</div>
            <div class="card-footer">
              <div class="price">${{p.price}}</div>
              <button class="add-btn" id="btn-${{p.id}}">Add to Order</button>
            </div>
          </div>
        </div>
      `).join('');
    }}

    function addToCart(card, id) {{
      cart++;
      document.getElementById('cart-count').textContent = '🛒 ' + cart;
      const btn = document.getElementById('btn-' + id);
      btn.textContent = '✓ Added';
      btn.classList.add('added');
      setTimeout(() => {{ btn.textContent = 'Add to Order'; btn.classList.remove('added'); }}, 2000);
      const t = document.getElementById('cart-toast');
      t.classList.add('show');
      setTimeout(() => t.classList.remove('show'), 3000);
    }}

    function scrollToProducts() {{
      document.getElementById('products').scrollIntoView({{behavior:'smooth'}});
    }}

    {auth_js}

    renderProducts();
  </script>
</body>
</html>"""

    return {"index.html": html}
