"""
MACOT multilingual test cases
=============================

This file contains 20 realistic customer scenarios for the MACOT cookie shop.

It is a test DATASET, not a fake AI implementation. To run automated assertions
against your Gemini agent, connect the `call_macot()` adapter below to the
public function in your agent/agent.py.

Install:
    pip install pytest

Run after connecting the adapter:
    pytest -v tests/test_macot_scenarios.py

Important:
- Use a test menu and test backend. Do not create real customer orders.
- Prices and delivery availability must come from the backend, not the LLM.
- Some expected values are intentionally "must_clarify": the agent must ask
  rather than guess.
"""

from __future__ import annotations

from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Adapter: connect this function to your existing agent implementation.
# ---------------------------------------------------------------------------

def call_macot(message: str, conversation_id: str = "test-session") -> dict[str, Any]:
    """
    Replace this body with a call to your agent's message-processing function.

    Expected return value: the parsed MACOT state dictionary, for example:
    {
        "reply": "...",
        "language": "English",
        "intent": "order",
        "items": [{"flavor_id": "kinder", "quantity": 6, "filling": None}],
        "delivery_date": "2026-11-15",
        "customer_name": "Sarah",
        "phone": None,
        "delivery_address": None,
        "missing_fields": ["phone", "delivery_address"],
        "ready_for_quote": False,
        "customer_approved_quote": False,
        "needs_human": False
    }

    If your agent currently runs only as an interactive CLI, expose its
    message-processing function separately first. Do not test by parsing
    decorative terminal output if you can return the state dictionary directly.
    """
    raise NotImplementedError(
        "Connect call_macot() to the message-processing function in agent/agent.py"
    )


# ---------------------------------------------------------------------------
# Shared expectations and helpers
# ---------------------------------------------------------------------------

def item_quantities(state: dict[str, Any]) -> dict[str, int]:
    """Convert MACOT's item list into {flavor_id: quantity} for easy comparison."""
    result: dict[str, int] = {}
    for item in state.get("items", []):
        flavor = item.get("flavor_id")
        quantity = item.get("quantity")
        if flavor and isinstance(quantity, int):
            result[flavor] = result.get(flavor, 0) + quantity
    return result


# ---------------------------------------------------------------------------
# 20 test scenarios
#
# Dates are described naturally in messages. For deterministic automated tests,
# freeze/mock the system date in your agent or compare relative date intent.
# Product IDs must match the IDs in your backend menu.
# ---------------------------------------------------------------------------

TEST_CASES = [
    {
        "id": "TC01",
        "group": "English",
        "name": "Complete order with some missing contact details",
        "messages": [
            "Hi! I'd like to order 6 Kinder cookies for tomorrow. "
            "My name is Sarah, and I live in Jounieh."
        ],
        "expected": {
            "language": "English",
            "intent": "order",
            "items": {"kinder": 6},
            "customer_name": "Sarah",
            "must_ask_for": ["phone", "delivery_address"],
            "must_not_confirm": True,
        },
    },
    {
        "id": "TC02",
        "group": "English",
        "name": "Ask for menu and prices",
        "messages": ["Hello! Can you show me your cookie flavors and prices?"],
        "expected": {
            "language": "English",
            "intent": "inquire_menu",
            "items": {},
            "must_use_backend_menu": True,
        },
    },
    {
        "id": "TC03",
        "group": "English",
        "name": "Order missing date and customer details",
        "messages": ["I want 3 Lotus cookies."],
        "expected": {
            "language": "English",
            "intent": "order",
            "items": {"lotus": 3},
            "must_ask_for": ["delivery_date"],
            "must_not_confirm": True,
        },
    },
    {
        "id": "TC04",
        "group": "English",
        "name": "Correct a quantity in a multi-message conversation",
        "messages": [
            "I want 2 Oreo cookies and 3 Kinder cookies for Saturday.",
            "Actually, make it 5 Kinder instead of 3.",
        ],
        "expected": {
            "language": "English",
            "intent": "order",
            "items": {"oreo": 2, "kinder": 5},
            "must_preserve_previous_items": True,
        },
    },
    {
        "id": "TC05",
        "group": "English",
        "name": "Ask about allergens",
        "messages": ["Do your Chocolate Chip cookies contain nuts?"],
        "expected": {
            "language": "English",
            "intent": "ask_product_information",
            "must_use_verified_allergen_data": True,
            "must_not_invent": True,
        },
    },
    {
        "id": "TC06",
        "group": "Arabic",
        "name": "Complete Arabic order",
        "messages": [
            "مرحباً، أريد طلب ٦ قطع من كوكيز كيندر ليوم غد. "
            "اسمي سارة وأسكن في جونية."
        ],
        "expected": {
            "language": "Arabic",
            "intent": "order",
            "items": {"kinder": 6},
            "customer_name": "سارة",
            "must_ask_for": ["phone", "delivery_address"],
            "must_not_confirm": True,
        },
    },
    {
        "id": "TC07",
        "group": "Arabic",
        "name": "Ask price for one and five Lotus cookies",
        "messages": ["كم سعر قطعة كوكيز اللوتس؟ وكم سعر ٥ قطع؟"],
        "expected": {
            "language": "Arabic",
            "intent": "ask_price",
            "must_use_backend_prices": True,
        },
    },
    {
        "id": "TC08",
        "group": "Arabic",
        "name": "Order multiple flavors",
        "messages": [
            "أريد ٣ قطع أوريو وقطعتين شوكولاتة و٤ قطع كيندر ليوم الأحد."
        ],
        "expected": {
            "language": "Arabic",
            "intent": "order",
            "items": {
                "oreo": 3,
                "chocolate_chip": 2,
                "kinder": 4,
            },
            "must_not_confirm": True,
        },
    },
    {
        "id": "TC09",
        "group": "Arabic",
        "name": "Cancel an existing order",
        "messages": ["أريد إلغاء طلبي، لم أعد بحاجة إلى الكوكيز."],
        "expected": {
            "language": "Arabic",
            "intent": "cancel_order",
            "must_check_existing_order": True,
            "must_use_backend_cancellation": True,
        },
    },
    {
        "id": "TC10",
        "group": "Arabic",
        "name": "Ask for a potentially unavailable flavor",
        "messages": ["هل لديكم كوكيز بالفستق؟ أريد طلب ٥ قطع."],
        "expected": {
            "language": "Arabic",
            "intent": "order",
            "items": {"pistachio": 5},
            "must_check_menu_availability": True,
            "must_not_invent_availability": True,
        },
    },
    {
        "id": "TC11",
        "group": "Arabizi",
        "name": "Complete Arabizi order with typos/variants",
        "messages": [
            "Marhaba bade 6 cookies kinder la bokra. "
            "Isme Sarah w sakne b Jounieh."
        ],
        "expected": {
            "language": "Arabizi",
            "intent": "order",
            "items": {"kinder": 6},
            "customer_name": "Sarah",
            "must_ask_for": ["phone", "delivery_address"],
        },
    },
    {
        "id": "TC12",
        "group": "Arabizi",
        "name": "Ask for flavors and prices in Arabizi",
        "messages": ["Shou 3andkon flavors w adde se3er kel wa7de?"],
        "expected": {
            "language": "Arabizi",
            "intent": "inquire_menu",
            "must_use_backend_menu": True,
        },
    },
    {
        "id": "TC13",
        "group": "Arabizi",
        "name": "Change quantity using Arabizi and English flavor names",
        "messages": [
            "Bade 2 Oreo w 3 Lotus.",
            "La khalas, khalli l Oreo 4 mesh 2.",
        ],
        "expected": {
            "language": "Arabizi",
            "intent": "order",
            "items": {"oreo": 4, "lotus": 3},
            "must_preserve_previous_items": True,
        },
    },
    {
        "id": "TC14",
        "group": "Arabizi",
        "name": "Ask about delivery location, date and time",
        "messages": ["Fikoun tousalo 3a Jounieh yom l jem3a 3al 5?"],
        "expected": {
            "language": "Arabizi",
            "intent": "ask_delivery_availability",
            "delivery_time": "17:00",
            "delivery_area": "Jounieh",
            "must_check_backend_slots": True,
        },
    },
    {
        "id": "TC15",
        "group": "Arabizi",
        "name": "Ask for final amount",
        "messages": ["Ma fhemet, ya3ne adde baddé edfa3 bel ekhir?"],
        "expected": {
            "language": "Arabizi",
            "intent": "ask_quote_explanation",
            "must_explain_item_total_and_fees": True,
            "must_use_backend_totals": True,
        },
    },
    {
        "id": "TC16",
        "group": "Lebanese Arabic",
        "name": "Complete order in Lebanese dialect",
        "messages": [
            "مرحبا، فيني وصّي ٦ كوكيز كيندر لبكرا؟ "
            "اسمي سارة وأنا بجونية."
        ],
        "expected": {
            "language": "Lebanese Arabic",
            "intent": "order",
            "items": {"kinder": 6},
            "customer_name": "سارة",
            "must_ask_for": ["phone", "delivery_address"],
        },
    },
    {
        "id": "TC17",
        "group": "Lebanese Arabic",
        "name": "Casual menu question",
        "messages": ["شو عندكن نكهات؟ وبقديش الحبة؟"],
        "expected": {
            "language": "Lebanese Arabic",
            "intent": "inquire_menu",
            "must_use_backend_menu": True,
        },
    },
    {
        "id": "TC18",
        "group": "Lebanese Arabic",
        "name": "Add another flavor to an existing order",
        "messages": [
            "بدي ٣ كيندر و٢ أوريو لبكرا.",
            "لا، بس زيدلي كمان ٢ لوتس.",
        ],
        "expected": {
            "language": "Lebanese Arabic",
            "intent": "order",
            "items": {"kinder": 3, "oreo": 2, "lotus": 2},
            "must_preserve_previous_items": True,
        },
    },
    {
        "id": "TC19",
        "group": "Lebanese Arabic",
        "name": "Ask about an existing order",
        "messages": ["مرحبا، أنا طالبة مبارح. فيك تخبرني وين صار طلبي؟"],
        "expected": {
            "language": "Lebanese Arabic",
            "intent": "check_order_status",
            "must_retrieve_existing_order": True,
            "must_not_invent_status": True,
        },
    },
    {
        "id": "TC20",
        "group": "Lebanese Arabic",
        "name": "Frustrated customer requests a human",
        "messages": [
            "عنجد تعبت وأنا عم جرّب اطلب! في حدا فيو يحكيني من الفريق؟"
        ],
        "expected": {
            "language": "Lebanese Arabic",
            "intent": "human_handoff",
            "needs_human": True,
        },
    },
]


# ---------------------------------------------------------------------------
# Typo, abbreviation, mixed-language and ambiguity regression tests.
# These supplement the 20 main scenarios.
# ---------------------------------------------------------------------------

TYPO_CASES = [
    {
        "id": "TYPO01",
        "message": "I wnt 6 kinder cookis for tomorow",
        "expected_items": {"kinder": 6},
        "expected_language": "English",
    },
    {
        "id": "TYPO02",
        "message": "Bade 4 cokies oreo",
        "expected_items": {"oreo": 4},
        "expected_language": "Arabizi",
    },
    {
        "id": "TYPO03",
        "message": "مرحبا بدي ٥ كوكز كيندر لبكرا",
        "expected_items": {"kinder": 5},
        "expected_language": "Lebanese Arabic",
    },
    {
        "id": "TYPO04",
        "message": "bde 3 kinder w 2 orio",
        "expected_items": {"kinder": 3, "oreo": 2},
        "expected_language": "Arabizi",
    },
    {
        "id": "TYPO05",
        "message": "I want 2 choco chip and 3 knder",
        "expected_items": {"chocolate_chip": 2, "kinder": 3},
        "expected_language": "English",
    },
    {
        "id": "TYPO06",
        "message": "bade 5 mn l otro",
        "must_clarify": True,
        "reason": "The flavor is unclear; the agent must not guess.",
    },
    {
        "id": "TYPO07",
        "message": "I want 4 Oreo... sorry 2 Oreo",
        "expected_items": {"oreo": 2},
        "reason": "Use the customer's explicit correction.",
    },
    {
        "id": "TYPO08",
        "message": "Can you توصلوا لعندنا بكرا؟",
        "must_clarify_or_check_context": True,
        "reason": "Mixed-language delivery question; location may be missing.",
    },
]


# ---------------------------------------------------------------------------
# Automated tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", TEST_CASES, ids=lambda c: c["id"])
def test_macot_scenario(case: dict[str, Any]) -> None:
    """Run each scenario as a sequence in one conversation session."""
    state: dict[str, Any] = {}

    for message in case["messages"]:
        state = call_macot(message, conversation_id=case["id"])

    expected = case["expected"]

    if "language" in expected:
        assert state.get("language") == expected["language"], (
            f'{case["id"]}: expected language {expected["language"]!r}, '
            f'got {state.get("language")!r}'
        )

    if "intent" in expected:
        assert state.get("intent") == expected["intent"], (
            f'{case["id"]}: expected intent {expected["intent"]!r}, '
            f'got {state.get("intent")!r}'
        )

    if "items" in expected:
        assert item_quantities(state) == expected["items"], (
            f'{case["id"]}: expected items {expected["items"]}, '
            f'got {item_quantities(state)}'
        )

    if "customer_name" in expected:
        assert state.get("customer_name") == expected["customer_name"]

    if expected.get("must_not_confirm"):
        assert state.get("customer_approved_quote") is False
        assert state.get("ready_for_quote") is False or state.get("customer_approved_quote") is False

    if expected.get("needs_human"):
        assert state.get("needs_human") is True


@pytest.mark.parametrize("case", TYPO_CASES, ids=lambda c: c["id"])
def test_typo_and_mixed_language_cases(case: dict[str, Any]) -> None:
    """Ensure obvious typos are understood and ambiguous text is clarified."""
    state = call_macot(case["message"], conversation_id=case["id"])

    if "expected_items" in case:
        assert item_quantities(state) == case["expected_items"]

    if "expected_language" in case:
        assert state.get("language") == case["expected_language"]

    if case.get("must_clarify"):
        # The exact intent label depends on your schema. The important behavior
        # is that MACOT does not invent a flavor or silently create an order.
        assert item_quantities(state) == {}, (
            f'{case["id"]}: ambiguous flavor was guessed: {item_quantities(state)}'
        )
        assert state.get("customer_approved_quote") is False


def test_agent_does_not_mark_order_approved_without_customer_confirmation() -> None:
    """A request or quote is not permission to save an order."""
    state = call_macot(
        "I want 2 Kinder cookies for tomorrow.",
        conversation_id="approval-safety",
    )
    assert state.get("customer_approved_quote") is False


def test_agent_preserves_items_when_customer_adds_an_item() -> None:
    """A later message adding a product must not erase earlier products."""
    first = call_macot(
        "I want 3 Kinder cookies.",
        conversation_id="preserve-items",
    )
    second = call_macot(
        "Add 2 Oreo cookies.",
        conversation_id="preserve-items",
    )
    assert item_quantities(first).get("kinder") == 3
    assert item_quantities(second) == {"kinder": 3, "oreo": 2}


if __name__ == "__main__":
    print(f"Loaded {len(TEST_CASES)} main scenarios.")
    print(f"Loaded {len(TYPO_CASES)} typo/mixed-language regression cases.")
    print("Connect call_macot() to agent/agent.py, then run: pytest -v")
