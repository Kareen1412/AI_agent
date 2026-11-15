"""MACOT clothing assistant. Requires a clothing-aware backend (see integration notes)."""
import json
import os
import uuid
import time
import re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google import genai
from google.genai import types, errors
from pydantic import BaseModel, Field

from prompts import SYSTEM
from tools import BackendError, MacotTools

load_dotenv(Path(__file__).resolve().parent.parent / '.env')


class ItemChange(BaseModel):
    product_id: str
    size: str | None = None
    color: str | None = None
    quantity: int | None = Field(default=None, ge=0)
    action: str = 'set'


class AgentOutput(BaseModel):
    reply: str
    language: str = 'english'
    intent: str = 'unclear'
    item_changes: list[ItemChange] = Field(default_factory=list)
    customer_name: str | None = None
    phone: str | None = None
    delivery_address: str | None = None
    approval_intent: bool = False
    needs_human: bool = False


class Session:
    def __init__(self, customer_id):
        self.customer_id = customer_id
        self.history = []
        self.items = []
        self.pending_items = []
        self.customer_name = None
        self.phone = customer_id if customer_id.isdigit() else None
        self.delivery_address = None
        self.order_id = None
        self.quote_version = None
        self.quote_summary = None
        self.awaiting_confirmation = False
        self.confirmed = False

    def state(self):
        return {key: getattr(self, key) for key in (
            'items', 'pending_items', 'customer_name', 'phone', 'delivery_address',
            'order_id', 'quote_version', 'quote_summary', 'awaiting_confirmation', 'confirmed')}


def catalog_index(products):
    if isinstance(products, dict):
        products = list(products.values())
    if not isinstance(products, list):
        raise ValueError('Backend products must be a list or mapping')
    return {p['product_id']: p for p in products if p.get('product_id')}


def resolve_variant(product, size, color):
    if size is None or color is None:
        return None
    matches = [v for v in product.get('variants', [])
               if str(v.get('size', '')).casefold() == str(size).casefold()
               and str(v.get('color', '')).casefold() == str(color).casefold()]
    return matches[0] if len(matches) == 1 else None


def apply_changes(items, pending, changes, catalog):
    result = [dict(i) for i in items]
    unresolved = [dict(i) for i in pending]
    for c in changes:
        if c.action not in {'add', 'set', 'remove'}:
            raise ValueError('Invalid item action')
        if c.product_id not in catalog:
            # Unsupported products cannot enter the basket.
            continue
        product = catalog[c.product_id]
        if not product.get('available', False):
            continue
        # Resolve contextual replies against a single pending product.
        size, color, quantity = c.size, c.color, c.quantity
        previous = [p for p in unresolved if p['product_id'] == c.product_id]
        if len(previous) == 1:
            size = size or previous[0].get('size')
            color = color or previous[0].get('color')
            if quantity is None:
                quantity = previous[0].get('quantity')
        if c.action == 'remove':
            if size and color:
                result = [i for i in result if not (i['product_id'] == c.product_id and
                          i['size'].casefold() == size.casefold() and i['color'].casefold() == color.casefold())]
                unresolved = [p for p in unresolved if not (p['product_id'] == c.product_id and
                              p.get('size') == size and p.get('color') == color)]
            else:
                matching = [i for i in result if i['product_id'] == c.product_id]
                if len(matching) == 1:
                    result.remove(matching[0])
            continue
        variant = resolve_variant(product, size, color)
        if quantity is None or quantity < 1 or variant is None:
            unresolved = [p for p in unresolved if p['product_id'] != c.product_id]
            unresolved.append({'product_id': c.product_id, 'size': size, 'color': color,
                               'quantity': quantity, 'invalid_variant': bool(size and color and variant is None)})
            continue
        if not variant.get('sku'):
            raise ValueError('Catalog variant has no SKU')
        # Stock is authoritative only at backend quote/confirmation, never here.
        sku = variant['sku']
        existing = next((i for i in result if i['sku'] == sku), None)
        if existing:
            result.remove(existing)
        new_qty = (existing['quantity'] if existing else 0) + quantity if c.action == 'add' else quantity
        result.append({'product_id': c.product_id, 'sku': sku, 'size': variant['size'],
                       'color': variant['color'], 'quantity': new_qty})
        unresolved = [p for p in unresolved if p['product_id'] != c.product_id]
    return result, unresolved


def missing_fields(s):
    missing = []
    if not s.items and not s.pending_items:
        missing.append('items')
    for p in s.pending_items:
        if p.get('quantity') is None:
            missing.append('quantity')
        if not p.get('size'):
            missing.append('size')
        if not p.get('color'):
            missing.append('color')
        if p.get('size') and p.get('color') and p.get('invalid_variant'):
            missing.append('valid_variant')
    if not s.customer_name:
        missing.append('customer_name')
    if not s.phone:
        missing.append('phone')
    if not s.delivery_address:
        missing.append('delivery_address')
    return list(dict.fromkeys(missing))


def ask_missing(missing, language):
    language = language.lower().strip()
    arabizi = language in {'arabizi', 'lebanese', 'lebanese arabic', 'lebanese_arabic', 'leb_arabic'}
    arabic = language in {'arabic', 'ar'}
    labels = {
        'items': ('شو القطعة اللي بدك ياها؟', 'Shu l item yalli baddik yeh?', 'Which item would you like?'),
        'quantity': ('قديش بدك عدد؟', 'Adde baddik?', 'How many would you like?'),
        'size': ('شو القياس؟', 'Shu l size?', 'What size would you like?'),
        'color': ('أي لون بدك؟', 'Aya lawn baddik?', 'Which color would you like?'),
        'valid_variant': ('هالقياس واللون مش موجودين سوا. بدك خيار تاني؟', 'Hal size w color mesh available sawa. Baddek option tene?', 'That size/color combination is not listed. Would you like another option?'),
        'customer_name': ('شو اسمك؟', 'Shu esmik?', 'What is your name?'),
        'phone': ('شو رقم تلفونك؟', 'Shu ra2mik?', 'What is your phone number?'),
        'delivery_address': ('شو عنوان التوصيل الكامل؟', 'Shu l 3enwen l kemel lal delivery?', 'What is your full delivery address?'),
    }
    return ' '.join(labels[k][0 if arabic else 1 if arabizi else 2] for k in missing[:2])


class MacotAgent:
    def __init__(self):
        key = os.getenv('GEMINI_API_KEY')
        if not key:
            raise RuntimeError('Set GEMINI_API_KEY in project .env')
        self.client = genai.Client(api_key=key, http_options=types.HttpOptions(
            timeout=max(10000, int(os.getenv('GEMINI_TIMEOUT_MS', '20000')))))
        self.model = os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite')
        self.tools = MacotTools()
        self.sessions = {}
        self.max_model_attempts = max(1, min(4, int(os.getenv('GEMINI_MAX_ATTEMPTS', '3'))))

    def extract(self, s, message, products):
        context = {
            'current_date_lebanon': datetime.now(ZoneInfo('Asia/Beirut')).isoformat(),
            'live_product_catalog': products,
            'current_order_state': s.state(),
            'recent_conversation': s.history[-12:],
            'latest_customer_message': message,
            'instruction': 'Return ONLY changes in latest message, not accumulated cart.'
        }
        response = None
        for attempt in range(self.max_model_attempts):
            try:
                response = self.client.models.generate_content(
                    model=self.model, contents=json.dumps(context, ensure_ascii=False, default=str),
                    config=types.GenerateContentConfig(system_instruction=SYSTEM,
                        response_mime_type='application/json', response_schema=AgentOutput, temperature=0.1))
                break
            except errors.APIError as exc:
                # Only retry temporary model overload, never invalid models or quota exhaustion.
                if getattr(exc, 'code', None) not in (503, 500, 502, 504) or attempt + 1 >= self.max_model_attempts:
                    raise
                time.sleep(min(2 ** attempt, 4))
        if not response.text:
            raise ValueError('Gemini returned an empty response')
        return AgentOutput.model_validate_json(response.text)

    def chat(self, customer_id, message, message_id=None):
        s = self.sessions.setdefault(customer_id, Session(customer_id))
        message_id = message_id or f'cli-{uuid.uuid4().hex}'
        try:
            # This MUST be backed by GET /products, not the cookie GET /menu.
            products = self.tools.products()
            catalog = catalog_index(products)
            extracted = self.extract(s, message, products)
            # Follow the customer's script across turns; a model label of
            # 'Lebanese Arabic' does not imply Arabic letters.
            if re.search(r'[\u0600-\u06ff]', message):
                extracted.language = 'arabic'
            elif re.search(r'\b(bade|baddi|badde|adde|shu|shou|wen|eh|hayde|kamen|ra2em|esme|esmak)\b', message, re.I):
                extracted.language = 'arabizi'
            elif message.strip().lower() in {'yes', 'yes pls', 'ok', 'sure', 'pls', 'please', 'no', 'one', 'two'} and s.history:
                # Short answers inherit the conversation's language.
                extracted.language = getattr(s, 'last_language', 'arabizi')
            elif extracted.language.lower() == 'lebanese arabic':
                extracted.language = 'arabizi'
            s.last_language = extracted.language
            if extracted.needs_human or extracted.intent in {'cancel_order', 'returns', 'order_status'}:
                reply = extracted.reply or 'A team member will need to assist with this request.'
                self._record(s, message, reply)
                return self._result(s, reply, extracted, needs_human=True)
            if s.confirmed:
                if extracted.intent in {'greeting', 'general_question'} and self._is_thanks(message):
                    reply = self._post_confirmation_thanks(s, extracted.language)
                elif extracted.intent in {'add_to_cart', 'edit_cart', 'remove_item', 'checkout', 'approve_order'}:
                    reply = ('Your order ' + str(s.order_id) + ' is already confirmed. '
                             'For changes or a new order, please contact our team.')
                else:
                    reply = extracted.reply or self._post_confirmation_thanks(s, extracted.language)
                self._record(s, message, reply)
                return self._result(s, reply, extracted)
            changes = extracted.item_changes
            any_detail_change = bool(changes or any((extracted.customer_name, extracted.phone, extracted.delivery_address)))
            if extracted.approval_intent and not any_detail_change:
                if not (s.awaiting_confirmation and s.quote_version is not None and s.order_id):
                    reply = 'I need to show you the verified order summary before confirming.'
                else:
                    result = self.tools.confirm(order_id=s.order_id, customer_id=customer_id,
                        quote_version=s.quote_version, confirmation_message_id=message_id)
                    if not result.get('success', False):
                        raise BackendError(result.get('message', 'Confirmation failed'))
                    s.confirmed, s.awaiting_confirmation = True, False
                    reply = self._confirmation_thanks(s, extracted.language)
                self._record(s, message, reply)
                return self._result(s, reply, extracted)
            new_items, new_pending = apply_changes(s.items, s.pending_items, changes, catalog)
            new_name = extracted.customer_name or s.customer_name
            new_phone = extracted.phone or s.phone
            new_address = extracted.delivery_address or s.delivery_address
            changed = (new_items != s.items or new_pending != s.pending_items or
                       new_name != s.customer_name or new_phone != s.phone or new_address != s.delivery_address)
            if changed:
                # Never quote an incomplete variant; keep it in session only.
                if new_items and not new_pending:
                    draft = self.tools.save_draft(customer_id=customer_id, order_id=s.order_id,
                        items=new_items, customer_name=new_name, phone=new_phone,
                        delivery_address=new_address)
                    s.order_id = draft['order_id']
                s.items, s.pending_items = new_items, new_pending
                s.customer_name, s.phone, s.delivery_address = new_name, new_phone, new_address
                s.quote_version = s.quote_summary = None
                s.awaiting_confirmation = False
            missing = missing_fields(s)
            if not missing and s.order_id and (changed or extracted.intent in {'checkout', 'approve_order'}):
                # Backend validates SKU stock, prices, shipping fee, and quote version.
                try:
                    quote = self.tools.quote(s.order_id)
                except BackendError as exc:
                    stock_reply = self._stock_error_reply(exc, extracted.language)
                    if stock_reply:
                        self._record(s, message, stock_reply)
                        return self._result(s, stock_reply, extracted)
                    if 'delivery_fees.flat' in str(exc):
                        reply = ('The shop delivery fee is not configured yet. I saved your order details; '
                                 'the shop must set the delivery fee before I can show a total.')
                        self._record(s, message, reply)
                        return self._result(s, reply, extracted, needs_human=True)
                    raise
                s.quote_version = quote['quote_version']
                s.quote_summary = quote['summary']
                s.awaiting_confirmation = True
                reply = f"{s.quote_summary}\n\nWould you like to confirm this order?"
            elif s.awaiting_confirmation and not changed:
                reply = f'{s.quote_summary}\n\nReply yes to confirm or tell me what to change.'
            elif missing and (changed or extracted.intent in {'add_to_cart', 'edit_cart', 'remove_item', 'checkout', 'approve_order'}):
                reply = ask_missing(missing, extracted.language)
            else:
                reply = extracted.reply
            self._record(s, message, reply)
            return self._result(s, reply, extracted)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            if isinstance(exc, BackendError):
                stock_reply = self._stock_error_reply(exc, getattr(s, 'last_language', 'english'))
                if stock_reply:
                    return {'reply': stock_reply, 'error': str(exc), 'order_id': s.order_id,
                            'order_status': 'confirmed' if s.confirmed else 'draft',
                            'state': s.state(), 'missing_fields': missing_fields(s)}
            if isinstance(exc, errors.APIError) and getattr(exc, 'code', None) == 503:
                reply = 'The assistant is temporarily busy. Please resend your last message in a moment; your existing order details are still saved.'
            else:
                reply = 'I could not complete that request safely. Please try again or contact the shop.'
            return {'reply': reply,
                    'error': str(exc), 'order_id': s.order_id,
                    'order_status': 'confirmed' if s.confirmed else 'draft'}

    @staticmethod
    def _is_thanks(message):
        text = message.casefold().strip()
        return bool(re.search(r"\b(thanks|thank you|thank u|thx|merci|mersi|shukran|choukran|ty)\b", text)) or any(
            word in text for word in ('شكرا', 'شكراً', 'يسلمو', 'مشكور', 'تسلم'))

    @staticmethod
    def _confirmation_thanks(s, language):
        lang = language.casefold()
        if lang in {'arabic', 'ar'}:
            return f'تم تأكيد طلبك رقم {s.order_id} بنجاح! شكراً لثقتك فينا ❤️'
        if lang in {'arabizi', 'lebanese', 'lebanese arabic', 'lebanese_arabic'}:
            return f'Ta2akkad talabik {s.order_id}! Merci ktir 3a thi2tik fina ❤️'
        return f'Your order {s.order_id} is confirmed! Thank you for shopping with us ❤️'

    @staticmethod
    def _post_confirmation_thanks(s, language):
        lang = language.casefold()
        if lang in {'arabic', 'ar'}:
            return f'أهلاً وسهلاً! شكراً إلك ❤️ طلبك {s.order_id} تأكّد.'
        if lang in {'arabizi', 'lebanese', 'lebanese arabic', 'lebanese_arabic'}:
            return f'Ahla w sahla! Merci elik ❤️ Talabik {s.order_id} ta2akkad.'
        return f'You’re very welcome! ❤️ Your order {s.order_id} is confirmed.'

    @staticmethod
    def _stock_error_reply(exc, language):
        # Stock is authoritative ONLY when reported by the backend.
        message = str(exc)
        if not any(term in message.casefold() for term in
                   ('insufficient stock', 'out of stock', 'product unavailable')):
            return None
        match = re.search(r'Insufficient stock for ([^;]+); available: (\d+)', message, re.I)
        arabic = language.casefold() in {'arabic', 'ar'}
        arabizi = language.casefold() in {'arabizi', 'lebanese', 'lebanese arabic', 'lebanese_arabic'}
        if match:
            sku, available = match.groups()
            if arabic:
                return f'للأسف، الكمية المتوفرة من {sku} هي {available} فقط. بدك كمية أقل أو قياس/لون تاني؟'
            if arabizi:
                return f'La2anno men {sku} fi bas {available} bel stock. Baddek adad a2al aw size/color tene?'
            return f'Sorry, only {available} of {sku} are in stock. Would you like fewer or another size/color?'
        if arabic:
            return 'للأسف هالقطعة مش متوفرة حالياً. بدك نشوف خيارات تانية؟'
        if arabizi:
            return 'La2anno hal item mesh available halla2. Baddek nchouf options tenye?'
        return 'Sorry, that item is currently unavailable. Would you like to see other options?'

    @staticmethod
    def _record(s, message, reply):
        s.history.extend([{'role': 'customer', 'message': message},
                          {'role': 'assistant', 'message': reply}])

    @staticmethod
    def _result(s, reply, extracted, needs_human=False):
        return {'reply': reply, 'language': extracted.language, 'intent': extracted.intent,
                'order_id': s.order_id,
                'order_status': 'confirmed' if s.confirmed else 'awaiting_confirmation' if s.awaiting_confirmation else 'draft',
                'missing_fields': missing_fields(s), 'needs_human': needs_human, 'state': s.state()}


def main():
    agent = MacotAgent()
    print('MACOT clothing agent. Type exit to quit.')
    customer_id = input('WhatsApp ID [96170123456]: ').strip() or '96170123456'
    while True:
        message = input('Customer: ').strip()
        if message.lower() in {'exit', 'quit'}:
            break
        if message:
            result = agent.chat(customer_id, message)
            print('MACOT:', result['reply'])
            print('STATE:', json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
# insert comment here