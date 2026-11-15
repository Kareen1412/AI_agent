"""MACOT clothing store API. Run from backend/: python -m uvicorn main:app --reload --port 8000

Firestore products/{product_id} contain variants [{sku,size,color,stock}].
Only the backend computes prices and changes inventory. Protect endpoints before public deployment.
"""
import os
import secrets
from pathlib import Path
from dotenv import load_dotenv
from fastapi import Header

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(
    PROJECT_ROOT / "macot_integration" / ".env",
    override=True
)

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from google.cloud import firestore as gc_firestore
from firebase_client import db

app = FastAPI(title='MACOT Clothing Backend', version='2.0')


def now():
    return datetime.now(timezone.utc)


def fail(status, message):
    raise HTTPException(status_code=status, detail=message)


def config():
    return db.collection('shop_settings').document('config').get().to_dict() or {}


def money(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        fail(422, 'Invalid price or delivery fee configuration')
    if not amount.is_finite() or amount < 0:
        fail(422, 'Price and fees must be nonnegative finite numbers')
    return amount


class OrderItem(BaseModel):
    product_id: str
    sku: str
    size: str
    color: str
    quantity: int = Field(ge=1)


class DraftIn(BaseModel):
    customer_id: str = Field(min_length=1)
    order_id: str | None = None
    items: list[OrderItem] = Field(default_factory=list)
    customer_name: str | None = None
    phone: str | None = None
    delivery_address: str | None = None


class ConfirmIn(BaseModel):
    customer_id: str = Field(min_length=1)
    quote_version: int = Field(ge=1)
    confirmation_message_id: str = Field(min_length=1)


def normalize(items, product_docs=None, check_stock=True):
    """Authoritative SKU/size/color validation and pricing. No inventory mutation."""
    grouped = defaultdict(int)
    for item in items:
        i = item if isinstance(item, OrderItem) else OrderItem(**item)
        grouped[(i.product_id, i.sku, i.size, i.color)] += i.quantity
    normalized = []
    total = Decimal('0')
    for (product_id, sku, size, color), qty in sorted(grouped.items()):
        data = (product_docs[product_id] if product_docs is not None
                else (db.collection('products').document(product_id).get().to_dict()))
        if not data or not data.get('available', False):
            fail(409, f'Product unavailable: {product_id}')
        variants = [v for v in data.get('variants', []) if v.get('sku') == sku]
        if len(variants) != 1:
            fail(422, f'Unknown or duplicate SKU: {sku}')
        variant = variants[0]
        if str(variant.get('size', '')).casefold() != size.casefold() or str(variant.get('color', '')).casefold() != color.casefold():
            fail(422, f'Size/color does not match SKU: {sku}')
        if check_stock and int(variant.get('stock', 0)) < qty:
            fail(409, f'Insufficient stock for {sku}; available: {variant.get("stock", 0)}')
        if data.get('currency', 'USD') != 'USD':
            fail(422, f'Unsupported currency for {product_id}')
        price = money(data.get('price'))
        line_total = price * qty
        normalized.append({'product_id': product_id, 'product_name': data.get('name', product_id),
                           'sku': sku, 'size': variant['size'], 'color': variant['color'],
                           'quantity': qty, 'unit_price': float(price), 'subtotal': float(line_total)})
        total += line_total
    return normalized, sum(i['quantity'] for i in normalized), total


def shipping_fee(cfg):
    fees = cfg.get('delivery_fees') or {}
    if 'flat' not in fees:
        fail(422, 'Shop delivery fee is not configured. Set shop_settings/config.delivery_fees.flat in Firestore before quoting')
    return money(fees['flat'])


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/products')
def products():
    return {'items': [snap.to_dict() for snap in db.collection('products').stream()]}


@app.get('/products/{product_id}')
def product_detail(product_id: str):
    snap = db.collection('products').document(product_id).get()
    if not snap.exists:
        fail(404, 'Product not found')
    return snap.to_dict()


@app.post('/orders/draft')
def save_draft(payload: DraftIn):
    cfg = config()
    if not cfg.get('accepting_orders', False):
        fail(409, 'Shop is not accepting orders')
    normalized, count, subtotal = normalize(payload.items)
    if count and count < int(cfg.get('minimum_order_quantity', 1)):
        fail(422, 'Below minimum order quantity')
    if payload.order_id:
        ref = db.collection('orders').document(payload.order_id)
        snap = ref.get()
        if not snap.exists:
            fail(404, 'Order not found')
        old = snap.to_dict()
        if old.get('customer_id') != payload.customer_id:
            fail(403, 'Order belongs to another customer')
        if old.get('status') == 'confirmed':
            fail(409, 'Confirmed order cannot be edited')
        order_id = payload.order_id
    else:
        counter_ref = db.collection('counters').document('clothing_orders')
        @gc_firestore.transactional
        def allocate(tx):
            snap = counter_ref.get(transaction=tx)
            n = int((snap.to_dict() or {}).get('last_number', 0)) + 1
            tx.set(counter_ref, {'last_number': n}, merge=True)
            return f'CL-{n:03d}'
        order_id = allocate(db.transaction())
        ref = db.collection('orders').document(order_id)
    ref.set({'order_id': order_id, 'customer_id': payload.customer_id,
             'customer_name': payload.customer_name, 'phone': payload.phone,
             'delivery_address': payload.delivery_address, 'delivery_type': 'delivery',
             'items': normalized, 'total_items': count, 'subtotal': float(subtotal),
             'delivery_fee': None, 'total': None, 'currency': 'USD',
             'status': 'draft', 'inventory_reserved': False, 'quote_version': 0,
             'quoted_at': None, 'updated_at': now()}, merge=True)
    return {'order_id': order_id, 'status': 'draft'}


@app.post('/orders/{order_id}/quote')
def quote(order_id: str):
    ref = db.collection('orders').document(order_id)
    snap = ref.get()
    if not snap.exists:
        fail(404, 'Order not found')
    o = snap.to_dict()
    if o.get('status') == 'confirmed':
        fail(409, 'Order already confirmed')
    if not config().get('accepting_orders', False):
        fail(409, 'Shop is not accepting orders')
    for field in ('customer_name', 'phone', 'delivery_address'):
        if not o.get(field) or not str(o[field]).strip():
            fail(422, f'Missing {field}')
    normalized, count, subtotal = normalize(o.get('items', []))
    if not count:
        fail(422, 'Order has no items')
    cfg = config()
    if count < int(cfg.get('minimum_order_quantity', 1)):
        fail(422, 'Below minimum order quantity')
    fee = shipping_fee(cfg)
    total = subtotal + fee
    version = int(o.get('quote_version') or 0) + 1
    lines = [f"{i['quantity']} x {i['product_name']} ({i['size']}, {i['color']}) — ${i['subtotal']:.2f}"
             for i in normalized]
    summary = (f"Order {order_id}:\n" + '\n'.join(lines) +
               f"\nSubtotal: ${subtotal:.2f}\nDelivery: ${fee:.2f}\nTotal: ${total:.2f} USD" +
               f"\nDelivery address: {o['delivery_address']}")
    ref.update({'items': normalized, 'total_items': count, 'subtotal': float(subtotal),
                'delivery_fee': float(fee), 'total': float(total),
                'quote_version': version, 'quoted_at': now(), 'status': 'quoted',
                'updated_at': now()})
    return {'order_id': order_id, 'quote_version': version, 'summary': summary,
            'subtotal': float(subtotal), 'delivery_fee': float(fee), 'total': float(total)}


@app.post('/orders/{order_id}/confirm')
def confirm(order_id: str, payload: ConfirmIn):
    order_ref = db.collection('orders').document(order_id)
    message_ref = db.collection('processed_messages').document(payload.confirmation_message_id)
    cfg_ref = db.collection('shop_settings').document('config')

    @gc_firestore.transactional
    def commit(tx):
        # All Firestore reads happen before any writes.
        order_snap = order_ref.get(transaction=tx)
        if not order_snap.exists:
            fail(404, 'Order not found')
        o = order_snap.to_dict()
        if o.get('customer_id') != payload.customer_id:
            fail(403, 'Order belongs to another customer')
        if o.get('status') == 'confirmed':
            if o.get('confirmation_message_id') == payload.confirmation_message_id:
                return {'success': True, 'order_id': order_id, 'already_confirmed': True}
            fail(409, 'Order already confirmed')
        if o.get('status') != 'quoted' or int(o.get('quote_version') or 0) != payload.quote_version:
            fail(409, 'Quote missing or outdated')
        if not o.get('quoted_at') or not o.get('items'):
            fail(409, 'Incomplete quote')
        cfg_snap = cfg_ref.get(transaction=tx)
        cfg = cfg_snap.to_dict() or {}
        if not cfg.get('accepting_orders', False):
            fail(409, 'Shop is not accepting orders')
        fee = shipping_fee(cfg)
        product_ids = sorted({i['product_id'] for i in o['items']})
        refs = {pid: db.collection('products').document(pid) for pid in product_ids}
        docs = {pid: refs[pid].get(transaction=tx).to_dict() for pid in product_ids}
        normalized, count, subtotal = normalize(o['items'], product_docs=docs)
        if not count or count < int(cfg.get('minimum_order_quantity', 1)):
            fail(409, 'Invalid order quantity')
        total = subtotal + fee
        if money(o.get('total')) != total or money(o.get('delivery_fee')) != fee:
            fail(409, 'Prices or delivery fees changed; request a new quote')
        for original, fresh in zip(sorted(o['items'], key=lambda i: (i['product_id'], i['sku'], i['size'], i['color'])), normalized):
            if money(original.get('unit_price')) != money(fresh['unit_price']):
                fail(409, 'Product price changed; request a new quote')
        # Deduct each SKU once per product, in this same Firestore transaction.
        for pid in product_ids:
            data = docs[pid]
            needed = {i['sku']: i['quantity'] for i in normalized if i['product_id'] == pid}
            updated = []
            for variant in data.get('variants', []):
                v = dict(variant)
                if v.get('sku') in needed:
                    v['stock'] = int(v['stock']) - needed[v['sku']]
                updated.append(v)
            tx.update(refs[pid], {'variants': updated, 'updated_at': now()})
        tx.update(order_ref, {'status': 'confirmed', 'inventory_reserved': True,
                              'confirmed_at': now(), 'updated_at': now(),
                              'confirmation_message_id': payload.confirmation_message_id})
        tx.set(message_ref, {'message_id': payload.confirmation_message_id,
                             'customer_id': payload.customer_id, 'status': 'processed',
                             'order_id': order_id, 'processed_at': now()}, merge=True)
        return {'success': True, 'order_id': order_id, 'status': 'confirmed',
                'message': 'Order confirmed. Inventory deducted successfully. Thank you for your purchase!'}

    return commit(db.transaction())


@app.get('/orders')
def list_orders(limit: int = Query(default=50, ge=1, le=200)):
    # TODO: require authentication/authorization before public deployment.
    return {'orders': [s.to_dict() for s in db.collection('orders').limit(limit).stream()]}


# Owner dashboard endpoints. Never expose these without a strong admin token.
def require_admin(authorization: str | None):
    token = os.getenv("ADMIN_API_TOKEN", "").strip()
    if not token:
        fail(503, "ADMIN_API_TOKEN is not configured on the backend")
    if not authorization or not secrets.compare_digest(authorization, f"Bearer {token}"):
        fail(401, "Invalid admin token")


class StatusUpdate(BaseModel):
    status: str


@app.get('/admin/connection')
def admin_connection(authorization: str | None = Header(default=None)):
    require_admin(authorization)
    # Live reads; this is not seeded or placeholder data.
    product_docs = list(db.collection('products').stream())
    order_docs = list(db.collection('orders').limit(200).stream())
    return {'connected': True, 'products': len(product_docs),
            'orders_sampled': len(order_docs),
            'source': 'Firestore via backend/firebase_client.py'}


@app.patch('/admin/orders/{order_id}/status')
def admin_update_status(order_id: str, payload: StatusUpdate,
                        authorization: str | None = Header(default=None)):
    require_admin(authorization)
    allowed = {'confirmed': {'preparing', 'cancelled'},
               'preparing': {'out_for_delivery', 'cancelled'},
               'out_for_delivery': {'delivered'}}
    ref = db.collection('orders').document(order_id)

    @gc_firestore.transactional
    def update(tx):
        snap = ref.get(transaction=tx)
        if not snap.exists:
            fail(404, 'Order not found')
        current = (snap.to_dict() or {}).get('status')
        if payload.status not in allowed.get(current, set()):
            fail(409, f'Cannot change status from {current} to {payload.status}')
        # Cancellation does not restore inventory; that needs a separate idempotent workflow.
        tx.update(ref, {'status': payload.status, 'updated_at': now()})
        return {'order_id': order_id, 'status': payload.status, 'success': True}

    return update(db.transaction())
