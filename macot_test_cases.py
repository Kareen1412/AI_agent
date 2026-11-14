"""MACOT Gemini integration tests. Calls REAL Gemini, but NEVER the live backend.

Run from AI_agent root: python -m pytest -v -rA macot_test_cases.py
Requires GEMINI_API_KEY in .env and agent.py, prompts.py, tools.py importable.
Each scenario is one pytest test. Pytest prints the passed / failed / error counts.
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Any
import pytest

# This file lives in AI_agent/macot_test_cases.py.
# agent.py, prompts.py, and tools.py live in AI_agent/agent/.
ROOT = Path(__file__).resolve().parent
AGENT_DIR = ROOT / "agent"
if not (AGENT_DIR / "agent.py").is_file():
    raise FileNotFoundError(f"Expected agent code at {AGENT_DIR / 'agent.py'}")
sys.path.insert(0, str(AGENT_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
load_dotenv(AGENT_DIR / ".env")

from agent import MacotAgent

ALLOWED = {'chocolate_chip', 'double_chocolate', 'red_velvet', 'kinder', 'nutella', 'lotus'}

class FakeBackend:
    """In-memory backend: no HTTP or Firestore writes. Quotes are synthetic and not pricing tests."""
    def __init__(self):
        self.drafts = {}
        self.counter = 0
        self.confirm_calls = 0
    def save_draft(self, *, customer_id, order_id, items, delivery_date, customer_name, phone, delivery_address):
        assert all(i['flavor_id'] in ALLOWED for i in items), 'Agent sent unsupported flavor to backend'
        assert all(i.get('filling') is not None for i in items if i['flavor_id']=='red_velvet'), 'Unresolved filling sent to backend'
        if not order_id:
            self.counter += 1
            order_id = f'TEST-{self.counter:04d}'
        self.drafts[order_id] = dict(items=items, delivery_date=delivery_date, customer_name=customer_name,
                                     phone=phone, delivery_address=delivery_address, customer_id=customer_id)
        return {'order_id': order_id}
    def availability(self, delivery_date, quantity):
        return {'available': True}
    def quote(self, order_id):
        return {'quote_version': 1, 'summary': 'TEST QUOTE (not a real price)'}
    def confirm(self, **kwargs):
        self.confirm_calls += 1
        return {'success': True}

@pytest.fixture(scope='module')
def agent_instance():
    a = MacotAgent()
    a.tools = FakeBackend()
    return a

def call_macot(agent_instance, message: str, conversation_id: str) -> dict[str, Any]:
    result = agent_instance.chat(f'test-{conversation_id}', message)
    assert 'error' not in result, f"Agent error: {result.get('error')}"
    state = result.get('state', {})
    return {**result, **state}

def item_quantities(state):
    result = {}
    for item in state.get('items', []):
        result[item['flavor_id']] = result.get(item['flavor_id'], 0) + item['quantity']
    return result

TEST_CASES = [{'id': 'TC01',
  'group': 'English',
  'name': 'Complete order with some missing contact details',
  'messages': ["Hi! I'd like to order 6 Kinder cookies for tomorrow. My name is Sarah, and I live in "
               'Jounieh.'],
  'expected': {'items': {'kinder': 6},
               'customer_name': 'Sarah',
               'must_ask_for': ['delivery_address'],
               'must_not_confirm': True,
               'unsupported_flavors': []}},
 {'id': 'TC02',
  'group': 'English',
  'name': 'Ask for menu and prices',
  'messages': ['Hello! Can you show me your cookie flavors and prices?'],
  'expected': {'items': {}, 'must_use_backend_menu': True, 'unsupported_flavors': []}},
 {'id': 'TC03',
  'group': 'English',
  'name': 'Order missing date and customer details',
  'messages': ['I want 3 Lotus cookies.'],
  'expected': {'items': {'lotus': 3},
               'must_ask_for': ['delivery_date'],
               'must_not_confirm': True,
               'unsupported_flavors': []}},
 {'id': 'TC04',
  'group': 'English',
  'name': 'Correct a quantity in a multi-message conversation',
  'messages': ['I want 2 Oreo cookies and 3 Kinder cookies for Saturday.',
               'Actually, make it 5 Kinder instead of 3.'],
  'expected': {'items': {'kinder': 5},
               'must_preserve_previous_items': True,
               'unsupported_flavors': ['oreo']}},
 {'id': 'TC05',
  'group': 'English',
  'name': 'Ask about allergens',
  'messages': ['Do your Chocolate Chip cookies contain nuts?'],
  'expected': {'must_use_verified_allergen_data': True, 'must_not_invent': True}},
 {'id': 'TC06',
  'group': 'Arabic',
  'name': 'Complete Arabic order',
  'messages': ['مرحباً، أريد طلب ٦ قطع من كوكيز كيندر ليوم غد. اسمي سارة وأسكن في جونية.'],
  'expected': {'items': {'kinder': 6},
               'customer_name': 'سارة',
               'must_ask_for': ['delivery_address'],
               'must_not_confirm': True,
               'unsupported_flavors': []}},
 {'id': 'TC07',
  'group': 'Arabic',
  'name': 'Ask price for one and five Lotus cookies',
  'messages': ['كم سعر قطعة كوكيز اللوتس؟ وكم سعر ٥ قطع؟'],
  'expected': {'must_use_backend_prices': True}},
 {'id': 'TC08',
  'group': 'Arabic',
  'name': 'Order multiple flavors',
  'messages': ['أريد ٣ قطع أوريو وقطعتين شوكولاتة و٤ قطع كيندر ليوم الأحد.'],
  'expected': {'items': {'chocolate_chip': 2, 'kinder': 4},
               'must_not_confirm': True,
               'unsupported_flavors': ['oreo']}},
 {'id': 'TC09',
  'group': 'Arabic',
  'name': 'Cancel an existing order',
  'messages': ['أريد إلغاء طلبي، لم أعد بحاجة إلى الكوكيز.'],
  'expected': {'must_check_existing_order': True, 'must_use_backend_cancellation': True}},
 {'id': 'TC10',
  'group': 'Arabic',
  'name': 'Ask for a potentially unavailable flavor',
  'messages': ['هل لديكم كوكيز بالفستق؟ أريد طلب ٥ قطع.'],
  'expected': {'items': {},
               'must_check_menu_availability': True,
               'must_not_invent_availability': True,
               'unsupported_flavors': ['pistachio']}},
 {'id': 'TC11',
  'group': 'Arabizi',
  'name': 'Complete Arabizi order with typos/variants',
  'messages': ['Marhaba bade 6 cookies kinder la bokra. Isme Sarah w sakne b Jounieh.'],
  'expected': {'items': {'kinder': 6},
               'customer_name': 'Sarah',
               'must_ask_for': ['delivery_address'],
               'unsupported_flavors': []}},
 {'id': 'TC12',
  'group': 'Arabizi',
  'name': 'Ask for flavors and prices in Arabizi',
  'messages': ['Shou 3andkon flavors w adde se3er kel wa7de?'],
  'expected': {'must_use_backend_menu': True}},
 {'id': 'TC13',
  'group': 'Arabizi',
  'name': 'Change quantity using Arabizi and English flavor names',
  'messages': ['Bade 2 Oreo w 3 Lotus.', 'La khalas, khalli l Oreo 4 mesh 2.'],
  'expected': {'items': {'lotus': 3}, 'must_preserve_previous_items': True, 'unsupported_flavors': ['oreo']}},
 {'id': 'TC14',
  'group': 'Arabizi',
  'name': 'Ask about delivery location, date and time',
  'messages': ['Fikoun tousalo 3a Jounieh yom l jem3a 3al 5?'],
  'expected': {'delivery_area': 'Jounieh'}},
 {'id': 'TC15',
  'group': 'Arabizi',
  'name': 'Ask for final amount',
  'messages': ['Ma fhemet, ya3ne adde baddé edfa3 bel ekhir?'],
  'expected': {'must_explain_item_total_and_fees': True, 'must_use_backend_totals': True}},
 {'id': 'TC16',
  'group': 'Lebanese Arabic',
  'name': 'Complete order in Lebanese dialect',
  'messages': ['مرحبا، فيني وصّي ٦ كوكيز كيندر لبكرا؟ اسمي سارة وأنا بجونية.'],
  'expected': {'items': {'kinder': 6},
               'customer_name': 'سارة',
               'must_ask_for': ['delivery_address'],
               'unsupported_flavors': []}},
 {'id': 'TC17',
  'group': 'Lebanese Arabic',
  'name': 'Casual menu question',
  'messages': ['شو عندكن نكهات؟ وبقديش الحبة؟'],
  'expected': {'must_use_backend_menu': True}},
 {'id': 'TC18',
  'group': 'Lebanese Arabic',
  'name': 'Add another flavor to an existing order',
  'messages': ['بدي ٣ كيندر و٢ أوريو لبكرا.', 'لا، بس زيدلي كمان ٢ لوتس.'],
  'expected': {'items': {'kinder': 3, 'lotus': 2},
               'must_preserve_previous_items': True,
               'unsupported_flavors': ['oreo']}},
 {'id': 'TC19',
  'group': 'Lebanese Arabic',
  'name': 'Ask about an existing order',
  'messages': ['مرحبا، أنا طالبة مبارح. فيك تخبرني وين صار طلبي؟'],
  'expected': {'must_retrieve_existing_order': True, 'must_not_invent_status': True}},
 {'id': 'TC20',
  'group': 'Lebanese Arabic',
  'name': 'Frustrated customer requests a human',
  'messages': ['عنجد تعبت وأنا عم جرّب اطلب! في حدا فيو يحكيني من الفريق؟'],
  'expected': {'needs_human': True}}]

TYPO_CASES = [{'id': 'TYPO01',
  'message': 'I wnt 6 kinder cookis for tomorow',
  'expected_items': {'kinder': 6},
  'unsupported_flavors': []},
 {'id': 'TYPO02', 'message': 'Bade 4 cokies oreo', 'expected_items': {}, 'unsupported_flavors': ['oreo']},
 {'id': 'TYPO03',
  'message': 'مرحبا بدي ٥ كوكز كيندر لبكرا',
  'expected_items': {'kinder': 5},
  'unsupported_flavors': []},
 {'id': 'TYPO04',
  'message': 'bde 3 kinder w 2 orio',
  'expected_items': {'kinder': 3},
  'unsupported_flavors': ['oreo']},
 {'id': 'TYPO05',
  'message': 'I want 2 choco chip and 3 knder',
  'expected_items': {'chocolate_chip': 2, 'kinder': 3},
  'unsupported_flavors': []},
 {'id': 'TYPO06',
  'message': 'bade 5 mn l otro',
  'must_clarify': True,
  'reason': 'The flavor is unclear; the agent must not guess.'},
 {'id': 'TYPO07',
  'message': 'I want 4 Oreo... sorry 2 Oreo',
  'expected_items': {},
  'reason': "Use the customer's explicit correction.",
  'unsupported_flavors': ['oreo']},
 {'id': 'TYPO08',
  'message': 'Can you توصلوا لعندنا بكرا؟',
  'must_clarify_or_check_context': True,
  'reason': 'Mixed-language delivery question; location may be missing.'}]

@pytest.mark.parametrize('case', TEST_CASES, ids=lambda c: c['id'])
def test_macot_scenario(agent_instance, case):
    state = {}
    for message in case['messages']:
        state = call_macot(agent_instance, message, case['id'])
    expected = case['expected']
    actual = item_quantities(state)
    if 'items' in expected:
        assert actual == expected['items'], f"{case['id']} expected {expected['items']}, got {actual}; reply: {state.get('reply')}"
    for flavor in expected.get('unsupported_flavors', []):
        assert flavor not in actual, f'{case["id"]} accepted unsupported {flavor}'
    if 'customer_name' in expected:
        assert state.get('customer_name') == expected['customer_name']
    if expected.get('needs_human'):
        assert state.get('needs_human') is True
    if expected.get('must_not_confirm'):
        assert state.get('order_status') != 'confirmed'
    if expected.get('must_ask_for'):
        # Agent may have inferred an address from location (e.g. Jounieh).
        # Require either the field or a follow-up question; never require a phone
        # when WhatsApp customer ID is already available.
        for field in expected['must_ask_for']:
            if not state.get(field):
                assert field in state.get('missing_fields', []), f'{case["id"]} failed to request {field}'
    assert state.get('order_status') != 'confirmed' or not expected.get('must_not_confirm')

@pytest.mark.parametrize('case', TYPO_CASES, ids=lambda c: c['id'])
def test_typo_and_mixed_language_cases(agent_instance, case):
    state = call_macot(agent_instance, case['message'], case['id'])
    actual = item_quantities(state)
    if 'expected_items' in case:
        assert actual == case['expected_items'], f"{case['id']} expected {case['expected_items']}, got {actual}"
    for flavor in case.get('unsupported_flavors', []):
        assert flavor not in actual
    if case.get('must_clarify'):
        assert actual == {}, f'{case["id"]}: guessed ambiguous flavor: {actual}'
    assert state.get('order_status') != 'confirmed'

def test_agent_does_not_confirm_without_approval(agent_instance):
    state = call_macot(agent_instance, 'I want 2 Kinder cookies for tomorrow.', 'approval-safety')
    assert state['order_status'] != 'confirmed'

def test_agent_preserves_items_when_customer_adds_an_item(agent_instance):
    first = call_macot(agent_instance, 'I want 3 Kinder cookies.', 'preserve-items')
    second = call_macot(agent_instance, 'Add 2 Lotus cookies.', 'preserve-items')
    assert item_quantities(first) == {'kinder': 3}
    assert item_quantities(second) == {'kinder': 3, 'lotus': 2}
