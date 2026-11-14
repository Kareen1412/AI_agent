"""HTTP adapter for Person 2's FastAPI backend (the only Firestore writer).

Expected endpoints:
 GET /menu
 GET /availability?date=YYYY-MM-DD&quantity=N
 POST /orders/draft
 POST /orders/{order_id}/quote
 POST /orders/{order_id}/confirm

Backend MUST independently validate pricing, weekly capacity, quote version,
customer identity, and perform confirmation in a Firestore transaction.
"""
import os
import requests


class BackendError(Exception):
    def __init__(self, message: str, status_code: int | None = None, code: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class MacotTools:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.getenv('BACKEND_URL', 'http://127.0.0.1:8000')).rstrip('/')
        self.session = requests.Session()
        token = os.getenv('BACKEND_API_KEY')
        if token:
            self.session.headers.update({'X-API-Key': token})

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = self.session.request(method, self.base_url + path, timeout=12, **kwargs)
        except requests.RequestException as exc:
            raise BackendError(f'Backend unreachable: {exc}', code='BACKEND_UNREACHABLE') from exc
        try:
            data = response.json()
        except ValueError:
            raise BackendError('Backend returned invalid JSON', response.status_code, 'INVALID_JSON')
        if not response.ok:
            code = data.get('error') if isinstance(data, dict) else None
            if isinstance(code, dict):
                code = code.get('code')
            detail = data.get('message') or data.get('detail') or str(data) if isinstance(data, dict) else str(data)
            raise BackendError(str(detail), response.status_code, str(code) if code else None)
        if not isinstance(data, dict) and not isinstance(data, list):
            raise BackendError('Unexpected backend response', response.status_code)
        return data

    def menu(self) -> dict | list:
        return self._request('GET', '/menu')

    def availability(self, date: str, quantity: int) -> dict:
        return self._request('GET', '/availability', params={'date': date, 'quantity': quantity})

    def save_draft(self, *, customer_id: str, order_id: str | None, items: list[dict],
                   delivery_date: str | None, customer_name: str | None,
                   phone: str | None, delivery_address: str | None) -> dict:
        return self._request('POST', '/orders/draft', json={
            'customer_id': customer_id, 'order_id': order_id,
            'items': items, 'delivery_date': delivery_date,
            'customer_name': customer_name, 'phone': phone,
            'delivery_address': delivery_address,
        })

    def quote(self, order_id: str) -> dict:
        return self._request('POST', f'/orders/{order_id}/quote')

    def confirm(self, *, order_id: str, customer_id: str, quote_version: int,
                confirmation_message_id: str) -> dict:
        return self._request('POST', f'/orders/{order_id}/confirm', json={
            'customer_id': customer_id,
            'quote_version': quote_version,
            'confirmation_message_id': confirmation_message_id,
        })
