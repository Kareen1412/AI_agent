"""MACOT shop owner dashboard, backed by Person 2's FastAPI endpoints."""
import os
from datetime import date, timedelta
import httpx
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="MACOT Owner", page_icon="🍪", layout="wide")
st.title("🍪 MACOT — Owner Dashboard")
base_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
admin_token = os.getenv("ADMIN_API_TOKEN", "")
if not admin_token or admin_token == "replace_with_shared_backend_admin_token":
    st.error("Set ADMIN_API_TOKEN in .env before using the dashboard.")
    st.stop()
headers = {"Authorization": f"Bearer {admin_token}"}


def api(method, path, **kwargs):
    try:
        with httpx.Client(timeout=12) as client:
            r = client.request(method, f"{base_url}{path}", headers=headers, **kwargs)
            r.raise_for_status()
            return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        st.error(f"Backend request failed: {exc}")
        return None


tab_orders, tab_capacity, tab_menu = st.tabs(["📦 Orders", "📅 Daily capacity", "🍪 Menu"])
with tab_orders:
    selected_date = st.date_input("Delivery date", value=date.today())
    if st.button("Refresh orders"):
        st.rerun()
    data = api("GET", "/orders", params={"date": selected_date.isoformat()})
    if data is not None:
        orders = data if isinstance(data, list) else data.get("orders", [])
        if orders:
            rows = [{"ID": o.get("order_id"), "Customer": o.get("customer_name"),
                     "Date": o.get("delivery_date"), "Cookies": o.get("total_cookies"),
                     "Total": o.get("total"), "Status": o.get("status")}
                    for o in orders]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            ids = [o.get("order_id") for o in orders if o.get("order_id")]
            if ids:
                order_id = st.selectbox("Update order", ids)
                status = st.selectbox("New status", ["confirmed", "preparing", "out_for_delivery", "delivered", "cancelled"])
                if st.button("Save status"):
                    result = api("PATCH", f"/orders/{order_id}", json={"status": status})
                    if result is not None:
                        st.success("Order updated")
                        st.rerun()
        else:
            st.info("No orders found for this date.")
with tab_capacity:
    capacity_date = st.date_input("Capacity date", value=date.today() + timedelta(days=1))
    cap = api("GET", "/availability", params={"date": capacity_date.isoformat(), "quantity": 1})
    if cap is not None:
        c1, c2, c3 = st.columns(3)
        c1.metric("Available", "Yes" if cap.get("available") else "No")
        c2.metric("Remaining orders", cap.get("remaining_orders", "—"))
        c3.metric("Remaining cookies", cap.get("remaining_cookies", "—"))
    with st.form("capacity_form"):
        max_orders = st.number_input("Max orders", min_value=0, value=10)
        max_cookies = st.number_input("Max cookies", min_value=0, value=120)
        enabled = st.checkbox("Accept orders", value=True)
        if st.form_submit_button("Save capacity"):
            result = api("PATCH", f"/delivery-capacity/{capacity_date.isoformat()}", json={
                "max_orders": max_orders, "max_cookies": max_cookies, "enabled": enabled
            })
            if result is not None:
                st.success("Capacity updated")
with tab_menu:
    menu = api("GET", "/menu")
    if menu is not None:
        items = menu if isinstance(menu, list) else menu.get("items", [])
        if items:
            st.dataframe(pd.DataFrame(items), use_container_width=True, hide_index=True)
            flavor_id = st.selectbox("Edit flavor", [x.get("flavor_id") or x.get("id") for x in items])
            available = st.checkbox("Available", value=True)
            price = st.number_input("Price (USD)", min_value=0.0, value=3.0, step=0.5)
            if st.button("Save flavor"):
                result = api("PATCH", f"/menu/{flavor_id}", json={"available": available, "price": price})
                if result is not None:
                    st.success("Menu updated")
        else:
            st.info("No menu items returned.")
