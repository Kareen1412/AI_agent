"""MACOT shop-owner dashboard, backed by the existing FastAPI endpoints."""
import os
from datetime import date, timedelta

import httpx
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="MACOT | Owner Space", page_icon="🍪", layout="wide")

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
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #c2cdbb; }
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
        color: #a7b89c; font-size: .68rem; font-weight: 700;
        letter-spacing: .14em; text-transform: uppercase;
    }
    [data-testid="stSidebar"] .stRadio [role="radiogroup"] { gap: .35rem; }
    [data-testid="stSidebar"] .stRadio label {
        min-height: 2.8rem; padding: .12rem .65rem; border-radius: 10px;
        color: #e0e5d9; transition: background .14s ease;
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
    .side-caption { margin: .16rem 0 0; color: #a6b49b; font-size: .68rem; letter-spacing: .11em; text-transform: uppercase; }
    .side-foot {
        margin-top: 2rem; padding: .85rem .9rem; border: 1px solid rgba(255,255,255,.09);
        border-radius: 12px; background: rgba(255,255,255,.035);
        color: #c2cdbb; font-size: .73rem; line-height: 1.55;
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
    .hero-subtitle { margin: .38rem 0 0; color: #d5ddce; font-size: .86rem; }
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
admin_token = os.getenv("ADMIN_API_TOKEN", "dwabKBBAJs66v-TXlQJX9xy8ivbpYNbaF9oUlEDlMb8").strip()
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
            "Delivery date": order.get("delivery_date") or "—",
            "Cookies": order.get("total_cookies") or "—",
            "Total": money(order.get("total")),
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
    "Capacity": "Daily capacity",
    "Menu": "Cookie menu",
}
page_subtitles = {
    "Overview": "A clear view of what is moving through your shop.",
    "Orders": "Find a delivery, check its details, and update its status.",
    "Capacity": "Set a comfortable limit for every baking day.",
    "Menu": "Keep your flavors and prices ready for the next order.",
}
page_icons = {"Overview": "⌂", "Orders": "▤", "Capacity": "◷", "Menu": "✳"}

with st.sidebar:
    st.markdown(
        """
        <div class="side-brand">
          <div class="side-mark">🍪</div>
          <div>
            <p class="side-name">MACOT</p>
            <p class="side-caption">Owner space</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("### Workspace")
    page = st.radio(
        "Navigation",
        list(page_titles),
        format_func=lambda value: f"{page_icons[value]}   {value}",
        label_visibility="collapsed",
        key="macot_navigation",
    )
    st.markdown(
        """
        <div class="side-foot">
          <span class="status-dot"></span>Owner tools<br>
          <span style="color:#a6b49b">Manage today. Bake with confidence.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown(
    f"""
    <div class="hero">
      <div class="hero-copy">
        <p class="hero-eyebrow">MACOT &nbsp; / &nbsp; OWNER DASHBOARD</p>
        <h1 class="hero-title">{page_titles[page]}</h1>
        <p class="hero-subtitle">{page_subtitles[page]}</p>
      </div>
      <div class="hero-date">{date.today().strftime("%A, %B %d")}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if page == "Overview":
    orders_payload = api("GET", "/orders", params={"limit": 200})
    all_orders = records(orders_payload, "orders") if orders_payload is not None else []
    active_orders = [
        order for order in all_orders
        if str(order.get("status", "")).lower() not in {"delivered", "cancelled"}
    ]
    pending_count = sum(
        str(order.get("status", "")).lower() in {"draft", "quoted", "confirmed"}
        for order in all_orders
    )
    cookie_count = sum(number(order.get("total_cookies")) for order in active_orders)
    sales_total = sum(
        number(order.get("total")) for order in all_orders
        if str(order.get("status", "")).lower() != "cancelled"
    )

    heading("Shop overview", "Your numbers, at a glance", "Based on the latest orders returned by your shop API.")
    metric_cols = st.columns(4, gap="medium")
    metric_cols[0].metric("All orders", f"{len(all_orders):,}")
    metric_cols[1].metric("Need attention", f"{pending_count:,}")
    metric_cols[2].metric("Cookies in progress", f"{cookie_count:,.0f}")
    metric_cols[3].metric("Order value", money(sales_total))

    st.markdown("<br>", unsafe_allow_html=True)
    recent_col, capacity_col = st.columns([1.7, 1], gap="large")
    with recent_col:
        heading("Latest activity", "Recent orders", "The most recent orders available from your API.")
        if all_orders:
            recent_orders = sorted(
                all_orders,
                key=lambda order: str(order.get("delivery_date") or ""),
                reverse=True,
            )[:6]
            st.dataframe(
                pd.DataFrame(order_rows(recent_orders)),
                use_container_width=True,
                hide_index=True,
                height=min(340, 42 + 36 * len(recent_orders)),
            )
        elif orders_payload is not None:
            st.info("No orders have come through yet.")

    with capacity_col:
        tomorrow = date.today() + timedelta(days=1)
        heading("Next delivery day", tomorrow.strftime("%A, %B %d"), "A quick look at tomorrow's availability.")
        capacity = api(
            "GET", "/availability",
            params={"date": tomorrow.isoformat(), "quantity": 1},
        )
        if capacity is not None:
            is_available = bool(capacity.get("available"))
            status_color = "#617b56" if is_available else "#ae6758"
            status_text = "Accepting orders" if is_available else "At capacity"
            st.markdown(
                f"""
                <div style="padding:1rem 1.05rem;border:1px solid var(--line);border-radius:14px;background:var(--paper)">
                  <p class="panel-kicker">AVAILABILITY</p>
                  <p class="panel-value" style="color:{status_color}">{status_text}</p>
                  <p class="panel-note">For {tomorrow.strftime("%B %d")}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            remain_orders, remain_cookies = st.columns(2, gap="small")
            remain_orders.metric("Orders left", capacity.get("remaining_orders", "—"))
            remain_cookies.metric("Cookies left", capacity.get("remaining_cookies", "—"))

elif page == "Orders":
    heading("Fulfillment", "Track every delivery", "Filter by delivery date or search by customer, order, or status.")
    date_col, search_col, refresh_col = st.columns([1.05, 1.5, .75], gap="medium")
    with date_col:
        selected_date = st.date_input(
            "Delivery date", value=date.today(), key="orders_delivery_date"
        )
    with search_col:
        query = st.text_input(
            "Search orders", placeholder="Customer, order ID, or status",
            key="orders_search",
        ).strip().lower()
    with refresh_col:
        st.markdown("<div style='height:1.85rem'></div>", unsafe_allow_html=True)
        if st.button("↻  Refresh", use_container_width=True, key="refresh_orders"):
            st.rerun()

    payload = api(
        "GET", "/orders",
        params={"date": selected_date.isoformat(), "limit": 200},
    )
    orders = records(payload, "orders") if payload is not None else []
    # The backend may ignore the optional date parameter; keep the displayed day accurate.
    orders = [
        order for order in orders
        if not order.get("delivery_date")
        or str(order.get("delivery_date"))[:10] == selected_date.isoformat()
    ]
    if query:
        orders = [
            order for order in orders
            if query in " ".join(
                str(order.get(field) or "")
                for field in ("order_id", "customer_name", "status")
            ).lower()
        ]

    if orders:
        st.dataframe(
            pd.DataFrame(order_rows(orders)),
            use_container_width=True,
            hide_index=True,
            height=min(500, 42 + 36 * len(orders)),
        )
        st.markdown("#### Update an order")
        ids = [str(order.get("order_id")) for order in orders if order.get("order_id")]
        if ids:
            lookup = {
                str(order.get("order_id")): order
                for order in orders if order.get("order_id")
            }
            order_col, status_col, action_col = st.columns([1.6, 1.2, .8], gap="medium")
            with order_col:
                order_id = st.selectbox(
                    "Order",
                    ids,
                    format_func=lambda value: order_label(lookup[value]),
                    key="order_to_update",
                )
            statuses = [
                "confirmed", "preparing", "out_for_delivery", "delivered", "cancelled"
            ]
            current = str(lookup[order_id].get("status") or "").lower()
            default_index = statuses.index(current) if current in statuses else 0
            with status_col:
                status = st.selectbox(
                    "New status",
                    statuses,
                    index=default_index,
                    format_func=lambda value: value.replace("_", " ").title(),
                    key="new_order_status",
                )
            with action_col:
                st.markdown("<div style='height:1.85rem'></div>", unsafe_allow_html=True)
                if st.button("Save update", use_container_width=True, key="save_order_status"):
                    result = api(
                        "PATCH", f"/orders/{order_id}", json={"status": status}
                    )
                    if result is not None:
                        st.success("Order status updated.")
                        st.rerun()
    elif payload is not None:
        st.info("No orders match this date and search.")

elif page == "Capacity":
    heading("Production planning", "Set your daily limits", "Check what remains, then choose how much work to take on.")
    capacity_date = st.date_input(
        "Capacity date", value=date.today() + timedelta(days=1), key="capacity_date"
    )
    capacity = api(
        "GET", "/availability",
        params={"date": capacity_date.isoformat(), "quantity": 1},
    )
    if capacity is not None:
        avail_col, orders_col, cookies_col = st.columns(3, gap="medium")
        avail_col.metric("Orders open", "Yes" if capacity.get("available") else "No")
        orders_col.metric("Orders remaining", capacity.get("remaining_orders", "—"))
        cookies_col.metric("Cookies remaining", capacity.get("remaining_cookies", "—"))

    st.markdown("<br>", unsafe_allow_html=True)
    heading("Capacity settings", "Make room for the right amount", "These limits apply to the selected date.")
    with st.form("capacity_form"):
        order_limit_col, cookie_limit_col = st.columns(2, gap="large")
        with order_limit_col:
            max_orders = st.number_input("Maximum orders", min_value=0, value=10, step=1)
        with cookie_limit_col:
            max_cookies = st.number_input("Maximum cookies", min_value=0, value=120, step=10)
        enabled = st.toggle("Accept orders for this date", value=True)
        if st.form_submit_button("Save capacity"):
            result = api(
                "PATCH",
                f"/delivery-capacity/{capacity_date.isoformat()}",
                json={
                    "max_orders": max_orders,
                    "max_cookies": max_cookies,
                    "enabled": enabled,
                },
            )
            if result is not None:
                st.success("Daily capacity updated.")

elif page == "Menu":
    heading("Menu management", "Your flavors, your way", "See what's available and adjust pricing without leaving the dashboard.")
    menu_payload = api("GET", "/menu")
    if menu_payload is not None:
        items = records(menu_payload, "items")
        if items:
            st.dataframe(
                pd.DataFrame(items),
                use_container_width=True,
                hide_index=True,
                height=min(380, 42 + 36 * len(items)),
            )
            st.markdown("<br>", unsafe_allow_html=True)
            heading("Quick edit", "Update a flavor", "Choose an item, set its price, and control availability.")

            def flavor_label(item):
                name = (
                    item.get("name") or item.get("flavor")
                    or item.get("flavor_name") or "Cookie flavor"
                )
                price = item.get("price")
                return f"{name} · {money(price)}" if price is not None else str(name)

            flavor_col, availability_col, price_col = st.columns([1.5, 1, 1], gap="medium")
            with flavor_col:
                flavor_index = st.selectbox(
                    "Flavor",
                    range(len(items)),
                    format_func=lambda index: flavor_label(items[index]),
                    key="flavor_to_edit",
                )
            selected_flavor = items[flavor_index]
            flavor_id = selected_flavor.get("flavor_id") or selected_flavor.get("id")
            with availability_col:
                available = st.checkbox(
                    "Available",
                    value=bool(selected_flavor.get("available", True)),
                    key=f"flavor_available_{flavor_index}",
                )
            with price_col:
                price = st.number_input(
                    "Price (USD)",
                    min_value=0.0,
                    value=max(0.0, number(selected_flavor.get("price"), 3.0)),
                    step=0.5,
                    key=f"flavor_price_{flavor_index}",
                )
            if flavor_id is not None and st.button("Save flavor", key="save_flavor"):
                result = api(
                    "PATCH",
                    f"/menu/{flavor_id}",
                    json={"available": available, "price": price},
                )
                if result is not None:
                    st.success("Menu item updated.")
                    st.rerun()
        else:
            st.info("No menu items were returned by the API.")

st.markdown(
    '<p class="footer-note">MACOT OWNER SPACE &nbsp;·&nbsp; Baked with care, managed with clarity.</p>',
    unsafe_allow_html=True,
)
