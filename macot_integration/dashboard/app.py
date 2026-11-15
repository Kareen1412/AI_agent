"""MACOT clothing dashboard: live Firestore data through the FastAPI backend.

Run from project root: streamlit run dashboard/app.py
Requires BACKEND_URL and ADMIN_API_TOKEN in project .env.
"""
import os
from datetime import date
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env", override=True)
st.set_page_config(page_title="MACOT | Owner Space", page_icon="👕", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --canvas: #f5f2e9;
        --paper: #fffefa;
        --ink: #29372b;
        --muted: #7d8072;
        --line: #e7e1d4;
        --deep: #24392c;
        --deep-soft: #3e5743;
        --teal: #617b56;
        --teal-bright: #bac8a7;
        --lime: #e8d9b5;
        --amber: #c58b58;
        --red: #ae6758;
    }
    html, body, [class*="css"] {
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: var(--ink);
    }
    .stApp { background: var(--canvas); }
    [data-testid="stHeader"] { background: rgba(245,242,233,.92); }
    .block-container { padding: 1.75rem 3rem 3rem; max-width: 1560px; }
    h1, h2, h3, h4 { color: var(--ink); letter-spacing: -.035em; }
    h1 { font-size: 1.8rem !important; }
    h2 { font-size: 1.25rem !important; }
    p, [data-testid="stCaptionContainer"] { color: var(--muted); }

    [data-testid="stSidebar"] {
        background: var(--deep);
        border-right: 1px solid rgba(255,255,255,.07);
    }
    [data-testid="stSidebar"] > div:first-child { padding-top: 1.5rem; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #f2f7ee; }
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
        color: #eaf4e3; font-size: .68rem; font-weight: 700;
        letter-spacing: .14em; text-transform: uppercase;
    }
    [data-testid="stSidebar"] .stRadio [role="radiogroup"] { gap: .35rem; }
    [data-testid="stSidebar"] .stRadio label {
        min-height: 2.8rem; padding: .12rem .65rem; border-radius: 10px;
        color: #ffffff; transition: background .14s ease;
    }
    [data-testid="stSidebar"] .stRadio label:hover { background: rgba(255,255,255,.075); }
    [data-testid="stSidebar"] .stRadio label p { color: inherit !important; font-weight: 600; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
        color: #f7f4ea; font-size: .88rem; letter-spacing: .01em;
    }
    .side-brand { display: flex; gap: .8rem; align-items: center; padding: .1rem .15rem 1.7rem; }
    .side-mark {
        display: grid; place-items: center; width: 43px; height: 43px; border-radius: 14px;
        background: var(--lime); color: var(--deep);
        font-size: 1.34rem; line-height: 1;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] .side-name {
        color: #f7f4ea;
    }
    .side-name { margin: 0; color: #f7f4ea; font-size: 1.08rem; font-weight: 750; letter-spacing: .04em; }
    .side-caption { margin: .16rem 0 0; color: #f2f7ee; font-size: .68rem; letter-spacing: .11em; text-transform: uppercase; }
    .side-foot {
        margin-top: 2rem; padding: .85rem .9rem; border: 1px solid rgba(255,255,255,.09);
        border-radius: 12px; background: rgba(255,255,255,.035);
        color: #f2f7ee; font-size: .73rem; line-height: 1.55;
    }
    .hero {
        position: relative; overflow: hidden; display: flex; align-items: center;
        justify-content: space-between; gap: 1.4rem; margin: .1rem 0 1.5rem;
        padding: 1.55rem 1.8rem; border: 1px solid #455a45; border-radius: 21px;
        background:
            radial-gradient(ellipse at 93% 5%, rgba(232,217,181,.25), transparent 31%),
            linear-gradient(118deg, #263b2d 0%, #465d43 72%, #6a7651 100%);
        box-shadow: 0 12px 28px rgba(48,57,39,.12);
    }
    .hero::after {
        content: ""; position: absolute; width: 220px; height: 220px; right: 12%;
        bottom: -185px; border: 1px solid rgba(239,224,186,.24); border-radius: 50%;
        box-shadow: 0 0 0 22px rgba(239,224,186,.045), 0 0 0 48px rgba(239,224,186,.03);
    }
    .hero-copy, .hero-date { position: relative; z-index: 1; }
    .hero-eyebrow {
        margin: 0 0 .38rem; color: var(--teal-bright); font-size: .66rem;
        font-weight: 750; letter-spacing: .16em; text-transform: uppercase;
    }
    .hero-title { margin: 0; color: #faf7ee; font-size: 1.78rem; font-weight: 720; letter-spacing: -.045em; }
    .hero-subtitle { margin: .38rem 0 0; color: #ffffff; font-size: .86rem; }
    .hero-date {
        flex: 0 0 auto; padding: .65rem .9rem; border: 1px solid rgba(255,255,255,.16);
        border-radius: 999px; background: rgba(255,255,255,.07);
        color: #f1eee2; font-size: .77rem; font-weight: 650;
    }
    .section-label {
        margin: .25rem 0 .18rem; color: var(--teal); font-size: .66rem;
        font-weight: 750; letter-spacing: .15em; text-transform: uppercase;
    }
    .section-title { margin: 0; color: var(--ink); font-size: 1.1rem; font-weight: 720; }
    .section-subtitle { margin: .28rem 0 1rem; color: var(--muted); font-size: .82rem; }

    .stMetric {
        min-height: 126px; padding: 1.05rem 1.15rem;
        border: 1px solid var(--line); border-radius: 16px; background: var(--paper);
        box-shadow: 0 5px 17px rgba(58,49,35,.045);
    }
    [data-testid="stMetricLabel"] p { color: var(--muted); font-size: .74rem; font-weight: 650; }
    [data-testid="stMetricValue"] { color: var(--ink); font-size: 1.8rem; font-weight: 750; }
    [data-testid="stMetricDelta"] { font-size: .7rem; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--line); border-radius: 16px; background: var(--paper);
    }
    div[data-testid="stDataFrame"] { overflow: hidden; border: 1px solid var(--line); border-radius: 13px; }
    div[data-testid="stButton"] > button,
    div[data-testid="stFormSubmitButton"] > button {
        min-height: 2.65rem; padding: .5rem 1rem; border: 1px solid var(--teal);
        border-radius: 10px; background: var(--teal); color: #fff;
        font-weight: 680; transition: background .15s ease, transform .15s ease;
    }
    div[data-testid="stButton"] > button:hover,
    div[data-testid="stFormSubmitButton"] > button:hover {
        border-color: #435f43; background: #435f43; color: #fff; transform: translateY(-1px);
    }
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
        border-color: #ded7c8; border-radius: 10px; background: var(--paper);
    }
    [data-testid="stAlert"] { border-radius: 12px; }
    [data-testid="stDataFrame"] [role="grid"] { color: var(--ink); }
    .panel-kicker {
        margin: 0 0 .35rem; color: var(--teal); font-size: .65rem;
        font-weight: 750; letter-spacing: .14em; text-transform: uppercase;
    }
    .panel-value { margin: 0; color: var(--ink); font-size: 1.32rem; font-weight: 720; letter-spacing: -.03em; }
    .panel-note { margin: .28rem 0 0; color: var(--muted); font-size: .78rem; }
    .status-dot {
        display: inline-block; width: 8px; height: 8px; margin-right: .4rem;
        border-radius: 50%; background: var(--teal-bright); vertical-align: 1px;
    }
    .footer-note { margin-top: 2rem; color: #929283; font-size: .7rem; }
    @media (max-width: 900px) {
        .block-container { padding: 1.25rem 1.1rem 2.2rem; }
        .hero { padding: 1.25rem; }
        .hero-title { font-size: 1.45rem; }
    }
    @media (max-width: 600px) {
        .hero { align-items: flex-start; }
        .hero-date { display: none; }
        .hero-title { font-size: 1.3rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

base_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
admin_token = os.getenv("ADMIN_API_TOKEN", "").strip()
if not admin_token:
    st.error("Dashboard access is not configured. Set ADMIN_API_TOKEN in your .env file.")
    st.stop()

headers = {"Authorization": f"Bearer {admin_token}"}


def api(method, path, **kwargs):
    """Call the existing API without displaying request credentials."""
    try:
        with httpx.Client(timeout=12) as client:
            response = client.request(
                method, f"{base_url}{path}", headers=headers, **kwargs
            )
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        st.error(
            "Could not complete the dashboard request. Check the API connection "
            f"and try again. ({exc})"
        )
        return None


def records(payload, key):
    """Accept either a list response or a wrapped API response."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        values = payload.get(key, [])
        if isinstance(values, list):
            return [item for item in values if isinstance(item, dict)]
    return []


def number(value, default=0.0):
    try:
        if isinstance(value, str):
            value = value.replace("$", "").replace(",", "").strip()
        return float(value)
    except (TypeError, ValueError):
        return default


def money(value):
    return f"${number(value):,.2f}"


def order_label(order):
    customer = order.get("customer_name") or "Customer"
    order_id = order.get("order_id") or "—"
    return f"{customer} · #{order_id}"


def order_rows(orders):
    return [
        {
            "Order": f"#{order.get('order_id') or '—'}",
            "Customer": order.get("customer_name") or "—",
            "Items": order.get("total_items", 0),
            "Total": money(order.get("total")) if order.get("total") is not None else "Not quoted",
            "Status": str(order.get("status") or "unknown").replace("_", " ").title(),
        }
        for order in orders
    ]


def heading(kicker, title, subtitle):
    st.markdown(
        f'<p class="section-label">{kicker}</p>'
        f'<p class="section-title">{title}</p>'
        f'<p class="section-subtitle">{subtitle}</p>',
        unsafe_allow_html=True,
    )


page_titles = {
    "Overview": "Today at MACOT",
    "Orders": "Order management",
    "Inventory": "Clothing inventory",
}
page_subtitles = {
    "Overview": "A clear view of your clothing shop and orders.",
    "Orders": "Review orders and track their fulfillment.",
    "Inventory": "Available products, sizes, colors, and stock from Firestore.",
}
page_icons = {"Overview": "⌂", "Orders": "▤", "Inventory": "▦"}

with st.sidebar:
    st.markdown(
        """
        <div class="side-brand">
          <div class="side-mark">👕</div>
          <div>
            <p class="side-name">MACOT</p>
            <p class="side-caption">Owner space</p>
          </div>
        </div>
        """, unsafe_allow_html=True,
    )
    st.markdown("### Workspace")
    page = st.radio(
        "Navigation", list(page_titles),
        format_func=lambda value: f"{page_icons[value]}   {value}",
        label_visibility="collapsed", key="macot_navigation",
    )
    st.markdown(
        """<div class="side-foot"><span class="status-dot"></span>Owner tools<br>
        <span style="color:#f4f8ef">Manage your clothing shop with confidence.</span></div>""",
        unsafe_allow_html=True,
    )

st.markdown(
    f"""<div class="hero"><div class="hero-copy">
    <p class="hero-eyebrow">MACOT &nbsp; / &nbsp; OWNER DASHBOARD</p>
    <h1 class="hero-title">{page_titles[page]}</h1>
    <p class="hero-subtitle">{page_subtitles[page]}</p></div>
    <div class="hero-date">{date.today().strftime('%A, %B %d')}</div></div>""",
    unsafe_allow_html=True,
)


def inventory_rows(products, only_available=True):
    rows = []
    for product in products:
        if only_available and not product.get("available", False):
            continue
        for variant in product.get("variants", []):
            stock = int(number(variant.get("stock")))
            if only_available and stock <= 0:
                continue
            rows.append({
                "Product": product.get("name") or product.get("product_id", "—"),
                "Category": product.get("category", "—"),
                "SKU": variant.get("sku", "—"),
                "Size": variant.get("size", "—"),
                "Color": variant.get("color", "—"),
                "Price": money(product.get("price")),
                "In stock": stock,
            })
    return rows


# Check the backend/Firestore connection on every Streamlit rerun.
connection = api("GET", "/admin/connection")
if connection is None:
    st.warning("No live Firestore data can be displayed until the backend is reachable "
               "and ADMIN_API_TOKEN matches in both processes.")
    st.stop()
st.caption(f"● Live Firestore connection · {connection.get('products', 0)} products · "
           f"{connection.get('orders_sampled', 0)} recent orders")

if page == "Overview":
    orders_payload = api("GET", "/orders", params={"limit": 200})
    products_payload = api("GET", "/products")
    orders = records(orders_payload, "orders") if orders_payload is not None else []
    products = records(products_payload, "items") if products_payload is not None else []
    awaiting = sum(o.get("status") in ("draft", "quoted") for o in orders)
    confirmed_value = sum(number(o.get("total")) for o in orders
                          if o.get("status") in ("confirmed", "preparing", "out_for_delivery", "delivered"))
    available_variants = inventory_rows(products)
    heading("Shop overview", "Your numbers, at a glance", "Based on the latest data from your shop API.")
    cols = st.columns(4, gap="medium")
    cols[0].metric("Orders shown", len(orders))
    cols[1].metric("Awaiting confirmation", awaiting)
    cols[2].metric("Available variants", len(available_variants))
    cols[3].metric("Confirmed order value", money(confirmed_value))
    st.markdown("<br>", unsafe_allow_html=True)
    heading("Latest activity", "Recent orders", "Up to 6 orders from the latest API response.")
    if orders:
        recent = sorted(orders, key=lambda o: str(o.get("updated_at") or o.get("created_at") or ""), reverse=True)[:6]
        st.dataframe(pd.DataFrame(order_rows(recent)), use_container_width=True,
                     hide_index=True, height=min(340, 42 + 36 * len(recent)))
    elif orders_payload is not None:
        st.info("No orders found.")

elif page == "Orders":
    heading("Fulfillment", "Track every order", "Search by customer, order ID, or status.")
    search_col, refresh_col = st.columns([3, 1], gap="medium")
    with search_col:
        query = st.text_input("Search orders", placeholder="Customer, order ID, or status").strip().lower()
    with refresh_col:
        st.markdown("<div style='height:1.85rem'></div>", unsafe_allow_html=True)
        if st.button("↻ Refresh", use_container_width=True):
            st.rerun()
    payload = api("GET", "/orders", params={"limit": 200})
    orders = records(payload, "orders") if payload is not None else []
    if query:
        orders = [o for o in orders if query in " ".join(str(o.get(k) or "")
                  for k in ("order_id", "customer_name", "status", "phone")).lower()]
    if orders:
        st.dataframe(pd.DataFrame(order_rows(orders)), use_container_width=True,
                     hide_index=True, height=min(500, 42 + 36 * len(orders)))
        heading("Order details", "Selected order", "Inspect the items and delivery information.")
        lookup = {str(o["order_id"]): o for o in orders if o.get("order_id")}
        if lookup:
            oid = st.selectbox("Order", list(lookup), format_func=lambda k: order_label(lookup[k]))
            order = lookup[oid]
            st.write("**Customer:**", order.get("customer_name") or "—")
            st.write("**Phone:**", order.get("phone") or "—")
            st.write("**Address:**", order.get("delivery_address") or "—")
            lines = [{"Product": i.get("product_name", i.get("product_id", "—")),
                      "SKU": i.get("sku", "—"), "Size": i.get("size", "—"),
                      "Color": i.get("color", "—"), "Quantity": i.get("quantity", 0),
                      "Subtotal": money(i.get("subtotal"))} for i in order.get("items", [])]
            if lines:
                st.dataframe(pd.DataFrame(lines), use_container_width=True, hide_index=True)
            current = str(order.get("status") or "draft")
            next_statuses = {
                "confirmed": ["preparing", "cancelled"],
                "preparing": ["out_for_delivery", "cancelled"],
                "out_for_delivery": ["delivered"],
            }.get(current, [])
            if next_statuses:
                chosen = st.selectbox("Update fulfillment status", next_statuses,
                                      format_func=lambda x: x.replace("_", " ").title())
                if st.button("Save status update"):
                    result = api("PATCH", f"/admin/orders/{oid}/status", json={"status": chosen})
                    if result is not None:
                        st.success("Order updated.")
                        st.rerun()
            else:
                st.caption("No fulfillment status updates available for this order.")
    elif payload is not None:
        st.info("No orders match your search.")

elif page == "Inventory":
    heading("Product catalog", "Available inventory",
            "Every row is a clothing size/color variant currently in stock in Firestore.")
    refresh_col, search_col = st.columns([1, 3], gap="medium")
    with refresh_col:
        st.markdown("<div style='height:1.85rem'></div>", unsafe_allow_html=True)
        if st.button("↻ Refresh inventory", use_container_width=True):
            st.rerun()
    with search_col:
        query = st.text_input("Search inventory", placeholder="Product, category, SKU, size, color").strip().lower()
    payload = api("GET", "/products")
    if payload is not None:
        rows = inventory_rows(records(payload, "items"))
        if query:
            rows = [row for row in rows if query in " ".join(str(v) for v in row.values()).lower()]
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                         height=min(600, 42 + 36 * len(rows)))
            st.caption(f"Showing {len(rows)} in-stock variants. Stock is updated by the backend after confirmed orders.")
        else:
            st.info("No available inventory matches your search.")

st.markdown(
    '<p class="footer-note">MACOT OWNER SPACE &nbsp;·&nbsp; Clothing inventory and order management.</p>',
    unsafe_allow_html=True,
)
