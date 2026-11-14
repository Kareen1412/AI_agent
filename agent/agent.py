"""MACOT agent: structured multilingual extraction + backend-controlled orders.

CLI sessions are in-memory. For WhatsApp deployment, persist sessions in
conversations/{customer_id} and load them before each message; the backend must
also deduplicate WhatsApp message IDs and serialize processing per customer.
"""
import json
import os
import time

import httpx
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field

from prompts import SYSTEM
from tools import BackendError, MacotTools

load_dotenv()
FLAVORS = {'chocolate_chip', 'double_chocolate', 'red_velvet', 'kinder', 'nutella', 'lotus'}
FILLINGS = {'cream_cheese', 'white_chocolate', 'none'}


class ItemChange(BaseModel):
    flavor_id: str
    quantity: int = Field(ge=0)
    filling: str | None = None
    action: str = Field(description='One of: add, set, remove')


class AgentOutput(BaseModel):
    reply: str
    language: str
    intent: str
    item_changes: list[ItemChange] = Field(default_factory=list)
    delivery_date: str | None = None
    customer_name: str | None = None
    phone: str | None = None
    delivery_address: str | None = None
    approval_intent: bool = False
    needs_human: bool = False


class Session:
    def __init__(self, customer_id: str):
        self.customer_id = customer_id
        self.history: list[dict] = []
        self.items: list[dict] = []
        self.delivery_date: str | None = None
        self.customer_name: str | None = None
        self.phone: str | None = customer_id if customer_id.isdigit() else None
        self.delivery_address: str | None = None
        self.order_id: str | None = None
        self.quote_version: int | None = None
        self.quote_summary: str | None = None
        self.awaiting_confirmation = False
        self.confirmed = False

    def state(self) -> dict:
        return {k: getattr(self, k) for k in (
            'items', 'delivery_date', 'customer_name', 'phone',
            'delivery_address', 'order_id', 'quote_version',
            'awaiting_confirmation', 'confirmed'
        )}


def apply_changes(items: list[dict], changes: list[ItemChange]) -> list[dict]:
    """Pure transformation; never allow malformed model output to alter state."""
    result = [dict(item) for item in items]
    for change in changes:
        if change.flavor_id not in FLAVORS:
            raise ValueError(f'Unknown flavor: {change.flavor_id}')
        if change.flavor_id == 'red_velvet':
            if change.filling is not None and change.filling not in FILLINGS:
                raise ValueError('Invalid Red Velvet filling')
        elif change.filling is not None:
            raise ValueError(f'{change.flavor_id} does not support fillings')
        if change.action not in {'add', 'set', 'remove'}:
            raise ValueError(f'Unknown action: {change.action}')
        key = (change.flavor_id, change.filling)
        index = next((i for i, x in enumerate(result)
                      if (x['flavor_id'], x.get('filling')) == key), None)
        old = result[index]['quantity'] if index is not None else 0
        quantity = (old + change.quantity if change.action == 'add'
                    else change.quantity if change.action == 'set' else 0)
        if index is not None:
            result.pop(index)
        if quantity > 0:
            result.append({'flavor_id': change.flavor_id,
                           'quantity': quantity, 'filling': change.filling})
    return result


def resolve_filling_reply(items: list[dict], changes: list[ItemChange], message: str) -> list[ItemChange]:
    """Apply a filling-only answer to a pending red velvet item."""
    pending = [x for x in items if x['flavor_id'] == 'red_velvet' and x.get('filling') is None]
    if not pending:
        return changes
    # If Gemini already explicitly resolved the pending filling, use that.
    if any(c.flavor_id == 'red_velvet' and c.filling in FILLINGS for c in changes):
        chosen = [c for c in changes if c.flavor_id == 'red_velvet' and c.filling in FILLINGS]
        return [ItemChange(flavor_id='red_velvet', quantity=0, filling=None, action='remove')] + [
            ItemChange(flavor_id='red_velvet', quantity=pending[0]['quantity'],
                       filling=c.filling, action='set') if c.action != 'remove' else c
            for c in changes
        ]
    normalized = message.lower().replace('-', ' ').replace('_', ' ')
    cream = any(term in normalized for term in ('cream cheese', 'creamcheese', 'كريم تشيز', 'كريمة الجبنة'))
    white = any(term in normalized for term in ('white chocolate', 'white choco', 'chocolat blanc', 'شوكولا بيضا', 'شوكولاتة بيضاء'))
    no_filling = any(term in normalized for term in (
        'wala shi', 'wala chi', 'bala shi', 'bala chi', 'ma bade filling',
        'ma baddi filling', 'ma badde filling', 'without filling',
        'no filling', 'plain', 'nothing inside', 'no stuffing',
        'بلا حشوة', 'بدون حشوة', 'ولا شي', 'ما بدي حشوة',
    ))
    if sum((cream, white, no_filling)) != 1:
        return changes
    filling = 'none' if no_filling else 'cream_cheese' if cream else 'white_chocolate'
    return changes + [ItemChange(flavor_id='red_velvet', quantity=pending[0]['quantity'],
                                 filling=filling, action='set'),
                      ItemChange(flavor_id='red_velvet', quantity=0,
                                 filling=None, action='remove')]


def next_question(missing: list[str], language: str) -> str:
    arabizi = language.lower() in ('arabizi', 'lebanese', 'lebanese_arabic', 'leb_arabic')
    arabic = language.lower() in ('arabic', 'ar')
    if 'red_velvet_filling' in missing:
        return ('Baddik l red velvet cream cheese, white chocolate, aw bala filling? 🍪' if arabizi else
                'بدك الريد فلفت كريم تشيز، وايت شوكليت، أو بلا حشوة؟ 🍪' if arabic else
                'For the red velvet, would you like cream cheese, white chocolate, or no filling? 🍪')
    labels = {
        'items': 'cookies and quantities', 'delivery_date': 'delivery date',
        'customer_name': 'name', 'phone': 'phone number',
        'delivery_address': 'delivery address',
    }
    if not missing:
        return ''
    if arabizi:
        prompts = {'items': 'Shu cookies w adde?', 'delivery_date': 'La aya nhar baddik l delivery?',
                   'customer_name': 'Shu esmik?', 'phone': 'Shu ra2mik?',
                   'delivery_address': 'Wen l 3enwen lal delivery?'}
        return ' '.join(prompts[k] for k in missing[:2] if k in prompts)
    if arabic:
        prompts = {'items': 'شو الأنواع والكميات؟', 'delivery_date': 'لأي نهار بدك التوصيل؟',
                   'customer_name': 'شو اسمك؟', 'phone': 'شو رقمك؟',
                   'delivery_address': 'شو عنوان التوصيل؟'}
        return ' '.join(prompts[k] for k in missing[:2] if k in prompts)
    return 'Could you tell me your ' + ' and '.join(labels[k] for k in missing[:2] if k in labels) + '?'


def missing_fields(s: Session) -> list[str]:
    missing = []
    if not s.items:
        missing.append('items')
    if any(x['flavor_id'] == 'red_velvet' and x.get('filling') is None for x in s.items):
        missing.append('red_velvet_filling')
    if not s.delivery_date:
        missing.append('delivery_date')
    if not s.customer_name:
        missing.append('customer_name')
    if not s.phone:
        missing.append('phone')
    if not s.delivery_address:
        missing.append('delivery_address')
    return missing


class MacotAgent:
    def __init__(self):
        key = os.getenv('GEMINI_API_KEY')
        if not key:
            raise RuntimeError('Set GEMINI_API_KEY in .env')
        # Timeout is per model attempt, in milliseconds.
        timeout_ms = max(10000, int(os.getenv('GEMINI_TIMEOUT_MS', '12000')))
        self.client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(timeout=timeout_ms),
        )
        self.models = [
            model.strip()
            for model in os.getenv(
                "GEMINI_MODELS",
                "gemini-3.8-flash,gemini-3-flash-preview"
            ).split(",")
            if model.strip()
        ]
        self.tools = MacotTools()
        self.sessions: dict[str, Session] = {}

    def extract(self, s: Session, message: str) -> AgentOutput:
        now = datetime.now(ZoneInfo('Asia/Beirut')).strftime('%Y-%m-%d %A')
        prompt = json.dumps({
            'current_date_lebanon': now,
            'current_order_state': s.state(),
            'recent_conversation': s.history[-16:],
            'latest_customer_message': message,
            'instruction': 'Return changes from the latest message, NOT all accumulated items. '
                           'Do not re-add existing items unless customer requested an addition.'
        }, ensure_ascii=False)
        last_error = None

        for model in self.models:
            started = time.perf_counter()
            try:
                print(f"Trying model: {model}")

                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM,
                        response_mime_type="application/json",
                        response_schema=AgentOutput,
                        temperature=0.2,
                    ),
                )

                if not response.text:
                    raise ValueError("Gemini returned an empty response")

                output = AgentOutput.model_validate_json(response.text)
                print(f"Success with {model} in {time.perf_counter() - started:.2f}s")
                return output

            except errors.APIError as exc:
                if exc.code in (429, 503, 504):
                    print(f"{model} unavailable ({exc.code}) after "
                          f"{time.perf_counter() - started:.2f}s. Switching...")
                    last_error = exc
                    continue

                # 404 can indicate a model that was retired. Try the next one.
                if exc.code == 404:
                    print(f"{model} not found. Switching model...")
                    last_error = exc
                    continue
                # Other errors (e.g. bad API key) should be surfaced.
                raise
            except (httpx.TimeoutException, TimeoutError) as exc:
                print(f"{model} timed out after "
                      f"{time.perf_counter() - started:.2f}s. Switching...")
                last_error = exc
                continue

        raise RuntimeError(
            f"All configured Gemini models are unavailable. Last error: {last_error}"
        )

    def chat(self, customer_id: str, message: str, message_id: str | None = None) -> dict:
        s = self.sessions.setdefault(customer_id, Session(customer_id))
        message_id = message_id or f'cli-{uuid.uuid4().hex}'
        try:
            extracted = self.extract(s, message)
            if extracted.needs_human:
                reply = 'I can connect you with the shop owner. Please wait for a team member.'
                s.history.extend([{'role': 'customer', 'message': message},
                                  {'role': 'assistant', 'message': reply}])
                return self._result(s, reply, extracted, needs_human=True)

            # Approval only applies to a previously validated quote, and only
            # when the message contains no edits or new order details.
            if extracted.approval_intent and s.awaiting_confirmation and s.quote_version is not None \
                    and not extracted.item_changes and not any((
                        extracted.delivery_date, extracted.customer_name,
                        extracted.phone, extracted.delivery_address)):
                result = self.tools.confirm(
                    order_id=s.order_id, customer_id=customer_id,
                    quote_version=s.quote_version,
                    confirmation_message_id=message_id,
                )
                if not result.get('success', True):
                    raise BackendError(result.get('message', 'Could not confirm order'),
                                       code=result.get('error'))
                s.confirmed = True
                s.awaiting_confirmation = False
                reply = f'Your order {s.order_id} is confirmed! 🍪'
                s.history.extend([{'role': 'customer', 'message': message},
                                  {'role': 'assistant', 'message': reply}])
                return self._result(s, reply, extracted)

            if extracted.approval_intent and not s.awaiting_confirmation:
                reply = 'I need to show you a validated order summary before confirming.'
                s.history.extend([{'role': 'customer', 'message': message},
                                  {'role': 'assistant', 'message': reply}])
                return self._result(s, reply, extracted)

            if s.confirmed:
                reply = 'This order is already confirmed. Please contact the shop to change it or start a new order.'
                s.history.extend([{'role': 'customer', 'message': message},
                                  {'role': 'assistant', 'message': reply}])
                return self._result(s, reply, extracted)

            # Build proposed state first; no in-memory mutation until backend
            # accepts the draft. A quote is invalidated by any changed detail.
            changes = resolve_filling_reply(s.items, extracted.item_changes, message)
            new_items = apply_changes(s.items, changes)
            new_date = extracted.delivery_date or s.delivery_date
            new_name = extracted.customer_name or s.customer_name
            new_phone = extracted.phone or s.phone
            new_address = extracted.delivery_address or s.delivery_address
            changed = (new_items != s.items or new_date != s.delivery_date
                       or new_name != s.customer_name or new_phone != s.phone
                       or new_address != s.delivery_address)

            if changed:
                # Keep incomplete item choices in session; do not send an invalid
                # red-velvet item without filling to the backend.
                incomplete_filling = any(
                    x['flavor_id'] == 'red_velvet' and x.get('filling') is None
                    for x in new_items
                )
                if not incomplete_filling:
                    draft = self.tools.save_draft(
                        customer_id=customer_id, order_id=s.order_id,
                        items=new_items, delivery_date=new_date,
                        customer_name=new_name, phone=new_phone,
                        delivery_address=new_address,
                    )
                    s.order_id = draft['order_id']
                s.items, s.delivery_date = new_items, new_date
                s.customer_name, s.phone, s.delivery_address = new_name, new_phone, new_address
                s.awaiting_confirmation = False
                s.quote_version = None
                s.quote_summary = None

            missing = missing_fields(s)
            if not missing and s.order_id and (changed or not s.awaiting_confirmation):
                quantity = sum(x['quantity'] for x in s.items)
                availability = self.tools.availability(s.delivery_date, quantity)
                if not availability.get('available', False):
                    reply = ('That delivery week does not have enough cookies available. '
                             'Would you like another date or a smaller quantity?')
                else:
                    quote = self.tools.quote(s.order_id)
                    s.quote_version = quote['quote_version']
                    s.quote_summary = quote['summary']
                    s.awaiting_confirmation = True
                    reply = f"{s.quote_summary}\n\nWould you like to confirm this order?"
            elif s.awaiting_confirmation and not changed:
                reply = f'{s.quote_summary}\n\nPlease reply yes to confirm, or tell me what to change.'
            else:
                reply = extracted.reply
                if missing and (changed or extracted.intent not in {'menu_question', 'general_question', 'greeting'}):
                    reply = next_question(missing, extracted.language) or reply

            s.history.extend([{'role': 'customer', 'message': message},
                              {'role': 'assistant', 'message': reply}])
            return self._result(s, reply, extracted)
        except (BackendError, ValueError, RuntimeError, errors.APIError,
                httpx.TimeoutException, TimeoutError) as exc:
            # Do not append failed interactions as successful state changes.
            return {'reply': f'I could not process that safely: {exc}. Please try again.',
                    'error': str(exc), 'order_id': s.order_id,
                    'order_status': 'confirmed' if s.confirmed else 'draft'}

    @staticmethod
    def _result(s: Session, reply: str, extracted: AgentOutput, needs_human: bool = False) -> dict:
        return {
            'reply': reply, 'language': extracted.language, 'intent': extracted.intent,
            'order_id': s.order_id,
            'order_status': ('confirmed' if s.confirmed else
                             'awaiting_confirmation' if s.awaiting_confirmation else 'draft'),
            'missing_fields': missing_fields(s),
            'needs_human': needs_human,
            'state': s.state(),
        }


def main():
    agent = MacotAgent()
    print('MACOT agent (backend required at BACKEND_URL). Type exit to quit.')
    customer_id = input('Test customer WhatsApp ID [96170123456]: ').strip() or '96170123456'
    while True:
        message = input('Customer: ').strip()
        if message.lower() in {'exit', 'quit'}:
            break
        if not message:
            continue
        result = agent.chat(customer_id, message)
        print('MACOT:', result['reply'])
        print('STATE:', json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
