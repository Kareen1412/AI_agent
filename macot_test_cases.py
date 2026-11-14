"""20 MACOT clothing integration tests: REAL Gemini + REAL FastAPI + REAL Firestore.

Place in AI_agent/macot_firestore_test_cases.py. Run backend separately, then:
    python -m pytest -v -rA macot_test_cases.py

SAFETY: By default tests require FIRESTORE_EMULATOR_HOST in BOTH the backend
and this pytest process. They create/delete test orders and a dedicated test
product, and confirm an order (which changes stock). To use a live Firestore
project instead, explicitly set MACOT_ALLOW_LIVE_FIRESTORE_TESTS=1. Prefer an
isolated TEST Firebase project; do not use your production store.

Requires GEMINI_API_KEY, backend/ firebase_client.py, agent/agent.py,
agent/prompts.py, agent/tools.py, requests, pytest and google-cloud-firestore.
BACKEND_URL defaults to http://127.0.0.1:8000. Test cases are isolated by
customer IDs. Cleanup runs after tests, but cannot undo external side effects
such as messages or audit logs; do not run against production.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
AGENT_DIR = ROOT / 'agent'
BACKEND_DIR = ROOT / 'backend'
sys.path.insert(0, str(AGENT_DIR))
from agent import MacotAgent  # noqa: E402

BASE = os.getenv('BACKEND_URL', 'http://127.0.0.1:8000').rstrip('/')
TIMEOUT = 20


def request(method, path, *, expected=200, **kwargs):
    r = requests.request(method, BASE + path, timeout=TIMEOUT, **kwargs)
    assert r.status_code == expected, f'{method} {path}: {r.status_code} {r.text}'
    return r.json()


@pytest.fixture(scope='module')
def live():
    if not os.getenv('FIRESTORE_EMULATOR_HOST') and os.getenv('MACOT_ALLOW_LIVE_FIRESTORE_TESTS') != '1':
        pytest.fail('Safety stop: configure FIRESTORE_EMULATOR_HOST in BOTH processes, '
                    'or explicitly set MACOT_ALLOW_LIVE_FIRESTORE_TESTS=1 for an isolated test Firebase project.')
    sys.path.insert(0, str(BACKEND_DIR))
    from firebase_client import db
    health = request('GET', '/health')
    assert health.get('status') == 'ok'
    return db


@pytest.fixture(scope='module')
def catalog(live):
    items = request('GET', '/products')['items']
    index = {p['product_id']: p for p in items}
    for pid in ('basic_tshirt', 'oversized_hoodie', 'straight_jeans', 'summer_dress'):
        assert pid in index, f'Missing seeded clothing product: {pid}'
    return index


@pytest.fixture(scope='module')
def agent(live, catalog):
    a = MacotAgent()  # uses real Gemini and unmodified MacotTools HTTP adapter
    assert a.tools.base_url.rstrip('/') == BASE, 'Agent BACKEND_URL differs from test BACKEND_URL'
    return a


@pytest.fixture(scope='module')
def tracked(live):
    """Track documents created by tests and delete them afterward."""
    orders, messages, products = set(), set(), set()
    yield orders, messages, products
    for oid in orders:
        live.collection('orders').document(oid).delete()
    for mid in messages:
        live.collection('processed_messages').document(mid).delete()
    for pid in products:
        live.collection('products').document(pid).delete()


def chat(agent, tracked, customer_id, message):
    result = agent.chat(customer_id, message)
    if result.get('order_id'):
        tracked[0].add(result['order_id'])
    assert 'error' not in result, f'{message!r}: {result.get("error")}; {result.get("reply")}'
    return result


def quantities(result):
    totals = {}
    for item in result.get('state', {}).get('items', []):
        totals[item['sku']] = totals.get(item['sku'], 0) + item['quantity']
    return totals


# 16 distinct real-Gemini/real-Firestore conversation tests.
# These require the four products from seed_clothing_db.py.
SCENARIOS = [
    ('TC01', ['Hello, what clothes do you sell and how much are they?'], {}),
    ('TC02', ['I want 2 black cotton t-shirts size M.'], {'TSH-BLK-M': 2}),
    ('TC03', ['I want one black oversized hoodie.'], {}),  # missing size
    ('TC04', ['I want 2 size M cotton T-shirts.'], {}),  # missing color
    ('TC05', ['I want 2 black hoodies size M.', 'Actually make that 4, not 2.'], {'HOD-BLK-M': 4}),
    ('TC06', ['مرحبا، بدي تيشيرتين سود قياس M.'], {'TSH-BLK-M': 2}),
    ('TC07', ['بكم سعر الجينز؟'], {}),
    ('TC08', ['أريد فستان صيفي بيج مقاس S، قطعة واحدة.'], {'DRS-BGE-S': 1}),
    ('TC09', ['عندكم أحذية رياضية؟ بدي زوجين.'], {}),
    ('TC10', ['Marhaba bade jeans black size 30, one.'], {'JNS-BLK-30': 1}),
    ('TC11', ['Hi bade es2al b adde l pants?'], {}),
    ('TC12', ['hi bade es2al b adde l pants?', 'yes pls', 'bade black one size 30'], {'JNS-BLK-30': 1}),
    ('TC13', ['Bade 2 black tshirts size M.', 'Zid kamen grey hoodie size S, one.'], {'TSH-BLK-M': 2, 'HOD-GRY-S': 1}),
    ('TC14', ['شو القياسات المتوفرة للجينز الأسود؟'], {}),
    ('TC15', ['بدي تيشيرت أسود قياس S، واحد.', 'زيدلي جينز أزرق قياس 32 واحد.'], {'TSH-BLK-S': 1, 'JNS-BLU-32': 1}),
    ('TC16', ['I wnt 2 blak tshrts size M'], {'TSH-BLK-M': 2}),
]


@pytest.mark.parametrize('case_id,messages,expected', SCENARIOS, ids=[c[0] for c in SCENARIOS])
def test_agent_conversation(agent, tracked, case_id, messages, expected):
    customer_id = f'macot-test-{uuid.uuid4().hex}'
    result = None
    for message in messages:
        result = chat(agent, tracked, customer_id, message)
    assert quantities(result) == expected, f'{case_id}: {result["reply"]}; {result.get("state")}'
    assert result['order_status'] != 'confirmed', 'Never confirm without a verified quote and approval'
    # Every saved draft must be an actual Firestore document.
    if result.get('order_id'):
        doc = tracked_db_order(tracked, result['order_id'])
        assert doc.get('customer_id') == customer_id


def tracked_db_order(tracked, order_id):
    # Imported here to avoid Firebase initialization before the safety gate.
    from firebase_client import db
    snap = db.collection('orders').document(order_id).get()
    assert snap.exists, f'Order {order_id} was not persisted to Firestore'
    return snap.to_dict()


@pytest.fixture(scope='module')
def backend_order_fixture(live, tracked):
    """Dedicated product to avoid decrementing any seeded shop inventory."""
    run_id = uuid.uuid4().hex
    pid = f'macot_integration_{run_id}'
    sku = f'MACOT-TEST-{run_id[:12]}'
    product_ref = live.collection('products').document(pid)
    product_ref.set({'product_id': pid, 'name': 'Integration Test Shirt', 'category': 'tops',
                     'price': 10, 'currency': 'USD', 'available': True,
                     'variants': [{'sku': sku, 'size': 'M', 'color': 'Black', 'stock': 3}]})
    tracked[2].add(pid)
    cfg_ref = live.collection('shop_settings').document('config')
    cfg = cfg_ref.get().to_dict() or {}
    assert cfg.get('accepting_orders') is True, 'Set shop_settings/config.accepting_orders=true in TEST project'
    assert 'flat' in (cfg.get('delivery_fees') or {}), 'Configure delivery_fees.flat in TEST project'
    return {'pid': pid, 'sku': sku, 'customer_id': f'macot-test-{run_id}', 'stock': 3}


def draft_payload(ctx, quantity=1):
    return {'customer_id': ctx['customer_id'], 'items': [
        {'product_id': ctx['pid'], 'sku': ctx['sku'], 'size': 'M', 'color': 'Black', 'quantity': quantity}],
        'customer_name': 'Integration Test', 'phone': '96170000000',
        'delivery_address': 'Test Street, Test Building, Beirut'}


@pytest.fixture(scope='module')
def order_flow(backend_order_fixture, tracked):
    ctx = backend_order_fixture
    result = request('POST', '/orders/draft', json=draft_payload(ctx))
    oid = result['order_id']
    tracked[0].add(oid)
    return {**ctx, 'order_id': oid}


# 4 backend/Firestore tests. Ordered flow via module fixture and explicit dependencies.
def test_backend_draft_persisted(order_flow, tracked):  # TC17
    o = tracked_db_order(tracked, order_flow['order_id'])
    assert o['status'] == 'draft'
    assert o['items'][0]['sku'] == order_flow['sku']
    assert o['items'][0]['quantity'] == 1


def test_backend_quote_does_not_reduce_stock(order_flow, live):  # TC18
    result = request('POST', f'/orders/{order_flow["order_id"]}/quote')
    assert result['quote_version'] >= 1
    o = live.collection('orders').document(order_flow['order_id']).get().to_dict()
    assert o['status'] == 'quoted'
    p = live.collection('products').document(order_flow['pid']).get().to_dict()
    assert p['variants'][0]['stock'] == 3


def test_backend_confirm_reduces_stock_once(order_flow, live, tracked):  # TC19
    oid = order_flow['order_id']
    o = live.collection('orders').document(oid).get().to_dict()
    if o['status'] != 'quoted':
        request('POST', f'/orders/{oid}/quote')
        o = live.collection('orders').document(oid).get().to_dict()
    mid = f'macot-confirm-{uuid.uuid4().hex}'
    tracked[1].add(mid)
    payload = {'customer_id': order_flow['customer_id'],
               'quote_version': o['quote_version'], 'confirmation_message_id': mid}
    confirmed = request('POST', f'/orders/{oid}/confirm', json=payload)
    assert confirmed['success'] is True
    p = live.collection('products').document(order_flow['pid']).get().to_dict()
    assert p['variants'][0]['stock'] == 2
    # Duplicate delivery of the SAME message must not deduct stock again.
    again = request('POST', f'/orders/{oid}/confirm', json=payload)
    assert again['success'] is True
    p = live.collection('products').document(order_flow['pid']).get().to_dict()
    assert p['variants'][0]['stock'] == 2


def test_backend_rejects_out_of_stock(order_flow, tracked):  # TC20
    ctx = order_flow
    result = request('POST', '/orders/draft', expected=409, json=draft_payload(ctx, quantity=99))
    # HTTP error payload must identify insufficient stock, not create an order.
    assert 'stock' in str(result).lower()
