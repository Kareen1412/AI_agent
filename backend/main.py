"""MACOT FastAPI backend using the existing Firestore collections."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
import os

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from google.cloud import firestore as gc_firestore
from firebase_client import db

app = FastAPI(title='MACOT Backend', version='1.0')


def utcnow():
    return datetime.now(timezone.utc)


def fail(status, message):
    raise HTTPException(status_code=status, detail=message)


def week_id_for(date_text: str):
    try:
        d = date.fromisoformat(date_text)
    except ValueError:
        fail(422, 'delivery_date must be YYYY-MM-DD')
    return (d - timedelta(days=d.weekday())).isoformat()


def settings():
    return (db.collection('shop_settings').document('config').get().to_dict() or {})


def validate_items(items):
    if not items:
        return [], 0, Decimal('0')
    normalized = []
    count = 0
    subtotal = Decimal('0')
    for item in items:
        flavor = item.flavor_id
        doc = db.collection('menu').document(flavor).get()
        if not doc.exists:
            fail(422, f'Unknown flavor: {flavor}')
        data = doc.to_dict()
        if not data.get('available', False):
            fail(422, f'Flavor unavailable: {flavor}')
        filling = item.filling
        if flavor == 'red_velvet':
            if filling is None:
                fail(422, 'Red velvet filling has not been selected')
            if filling not in data.get('fillings', []):
                fail(422, f'Invalid filling: {filling}. Update menu/red_velvet.fillings if none is offered.')
        elif filling is not None:
            fail(422, f'{flavor} does not accept a filling')
        price = Decimal(str(data['price']))
        line_total = price * item.quantity
        normalized.append({'flavor_id': flavor, 'quantity': item.quantity,
                           'filling': filling, 'unit_price': float(price), 'subtotal': float(line_total)})
        count += item.quantity
        subtotal += line_total
    return normalized, count, subtotal


class OrderItem(BaseModel):
    flavor_id: str
    quantity: int = Field(ge=1)
    filling: str | None = None


class DraftIn(BaseModel):
    customer_id: str
    order_id: str | None = None
    items: list[OrderItem] = Field(default_factory=list)
    delivery_date: str | None = None
    customer_name: str | None = None
    phone: str | None = None
    delivery_address: str | None = None


class ConfirmIn(BaseModel):
    customer_id: str
    quote_version: int
    confirmation_message_id: str


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/menu')
def get_menu():
    return {'items': [d.to_dict() for d in db.collection('menu').stream()]}


@app.get('/availability')
def availability(date: str, quantity: int = Query(ge=1)):
    week_id = week_id_for(date)
    week = db.collection('production_weeks').document(week_id).get()
    if not week.exists:
        return {'available': False, 'week_id': week_id, 'reason': 'No production week configured'}
    w = week.to_dict()
    remaining = max(0, int(w['max_cookies']) - int(w.get('reserved_cookies', 0)))
    enabled = bool(w.get('enabled')) and bool(settings().get('accepting_orders', False))
    return {'available': enabled and quantity <= remaining, 'week_id': week_id,
            'remaining_cookies': remaining, 'reason': None if enabled else 'Ordering disabled'}


@app.post('/orders/draft')
def save_draft(payload: DraftIn):
    config = settings()
    if not config.get('accepting_orders', False):
        fail(409, 'Shop is not accepting orders')
    items, count, subtotal = validate_items(payload.items)
    if count and count < int(config.get('minimum_order_quantity', 1)):
        fail(422, 'Order below minimum quantity')
    week_id = week_id_for(payload.delivery_date) if payload.delivery_date else None
    if payload.delivery_date:
        requested = date.fromisoformat(payload.delivery_date)
        from zoneinfo import ZoneInfo
        now_local = datetime.now(ZoneInfo('Asia/Beirut'))
        hours_notice = (datetime.combine(requested, datetime.min.time(), tzinfo=ZoneInfo('Asia/Beirut')) - now_local).total_seconds() / 3600
        if hours_notice < int(config.get('minimum_notice_hours', 24)):
            fail(422, 'Delivery date does not meet minimum notice')
    if payload.order_id:
        ref = db.collection('orders').document(payload.order_id)
        old = ref.get()
        if not old.exists:
            fail(404, 'Order not found')
        existing = old.to_dict()
        if existing.get('customer_id') != payload.customer_id:
            fail(403, 'Order belongs to another customer')
        if existing.get('status') == 'confirmed':
            fail(409, 'Confirmed orders cannot be edited')
        order_id = payload.order_id
    else:
        # Transactional counter increment prevents duplicate order IDs.
        counter_ref = db.collection('counters').document('orders')
        tx = db.transaction()
        @gc_firestore.transactional
        def next_id(transaction):
            snap = counter_ref.get(transaction=transaction)
            n = int((snap.to_dict() or {}).get('last_number', 0)) + 1
            transaction.set(counter_ref, {'last_number': n}, merge=True)
            return f'CK-{n:03d}'
        order_id = next_id(tx)
        ref = db.collection('orders').document(order_id)
    ref.set({'order_id': order_id, 'customer_id': payload.customer_id,
             'customer_name': payload.customer_name, 'phone': payload.phone,
             'delivery_address': payload.delivery_address,
             'delivery_type': 'delivery', 'items': items, 'total_cookies': count,
             'delivery_date': payload.delivery_date, 'production_week_id': week_id,
             'subtotal': float(subtotal), 'delivery_fee': None, 'total': None,
             'currency': 'USD', 'status': 'draft', 'capacity_reserved': False,
             'quote_version': 0, 'quoted_at': None, 'updated_at': utcnow()}, merge=True)
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
    for key in ('customer_name', 'phone', 'delivery_address', 'delivery_date'):
        if not o.get(key):
            fail(422, f'Missing {key}')
    items, count, subtotal = validate_items([OrderItem(**x) for x in o.get('items', [])])
    if not count:
        fail(422, 'Order has no cookies')
    availability_result = availability(o['delivery_date'], count)
    if not availability_result['available']:
        fail(409, 'Insufficient capacity for delivery week')
    config = settings()
    fees = config.get('delivery_fees') or {}
    # Delivery price is not inferred from sample order; configure a flat fee explicitly.
    if 'flat' not in fees:
        fail(422, 'Set shop_settings/config.delivery_fees.flat before quoting')
    fee = Decimal(str(fees['flat']))
    if fee < 0:
        fail(422, 'Invalid delivery fee')
    total = subtotal + fee
    version = int(o.get('quote_version') or 0) + 1
    summary = (f"Order {order_id}: {count} cookies, subtotal ${subtotal:.2f}, "
               f"delivery ${fee:.2f}, total ${total:.2f} USD. "
               f"Delivery date: {o['delivery_date']}; address: {o['delivery_address']}.")
    ref.update({'items': items, 'total_cookies': count, 'subtotal': float(subtotal),
                'delivery_fee': float(fee), 'total': float(total), 'quote_version': version,
                'quoted_at': utcnow(), 'status': 'quoted', 'updated_at': utcnow()})
    return {'order_id': order_id, 'quote_version': version, 'summary': summary,
            'subtotal': float(subtotal), 'delivery_fee': float(fee), 'total': float(total)}


@app.post('/orders/{order_id}/confirm')
def confirm(order_id: str, payload: ConfirmIn):
    order_ref = db.collection('orders').document(order_id)
    msg_ref = db.collection('processed_messages').document(payload.confirmation_message_id)
    tx = db.transaction()

    @gc_firestore.transactional
    def commit(transaction):
        order_snap = order_ref.get(transaction=transaction)
        if not order_snap.exists:
            fail(404, 'Order not found')
        order = order_snap.to_dict()
        if order.get('customer_id') != payload.customer_id:
            fail(403, 'Order belongs to another customer')
        if order.get('status') == 'confirmed':
            if order.get('confirmation_message_id') == payload.confirmation_message_id:
                return {'success': True, 'order_id': order_id, 'already_confirmed': True}
            fail(409, 'Order already confirmed')
        if order.get('status') != 'quoted' or order.get('quote_version') != payload.quote_version:
            fail(409, 'Quote is missing or outdated')
        if not order.get('quoted_at') or not order.get('delivery_date'):
            fail(409, 'Quote is incomplete')
        week_ref = db.collection('production_weeks').document(order['production_week_id'])
        week_snap = week_ref.get(transaction=transaction)
        if not week_snap.exists:
            fail(409, 'Production week not configured')
        week = week_snap.to_dict()
        if not week.get('enabled'):
            fail(409, 'Production week disabled')
        if not settings().get('accepting_orders', False):
            fail(409, 'Ordering disabled')
        quantity = int(order['total_cookies'])
        if int(week.get('reserved_cookies', 0)) + quantity > int(week['max_cookies']):
            fail(409, 'Insufficient weekly capacity')
        transaction.update(week_ref, {'reserved_cookies': gc_firestore.Increment(quantity),
                                      'confirmed_orders': gc_firestore.Increment(1),
                                      'updated_at': utcnow()})
        transaction.update(order_ref, {'status': 'confirmed', 'capacity_reserved': True,
                                       'confirmed_at': utcnow(), 'updated_at': utcnow(),
                                       'confirmation_message_id': payload.confirmation_message_id})
        transaction.set(msg_ref, {'message_id': payload.confirmation_message_id,
                                  'customer_id': payload.customer_id, 'status': 'processed',
                                  'order_id': order_id, 'processed_at': utcnow()}, merge=True)
        return {'success': True, 'order_id': order_id, 'status': 'confirmed'}
    return commit(tx)


@app.get('/orders')
def list_orders(limit: int = Query(default=50, ge=1, le=200)):
    # Protect this endpoint with authentication before deploying publicly.
    return {'orders': [s.to_dict() for s in db.collection('orders').limit(limit).stream()]}
