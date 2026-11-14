"""HTTP adapter for MACOT clothing FastAPI backend."""
import os
import requests


class BackendError(Exception):
    def __init__(self, message: str, status_code=None, code=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class MacotTools:
    def __init__(self, base_url=None):
        self.base_url = (base_url or os.getenv('BACKEND_URL', 'http://127.0.0.1:8000')).rstrip('/')
        self.session = requests.Session()
        key = os.getenv('BACKEND_API_KEY')
        if key:
            self.session.headers.update({'X-API-Key': key})

    def _request(self, method, path, **kwargs):
        try:
            response = self.session.request(method, self.base_url + path, timeout=15, **kwargs)
        except requests.RequestException as exc:
            raise BackendError(f'Backend unreachable: {exc}') from exc
        if not response.ok:
            try:
                detail = response.json().get('detail', response.text)
            except ValueError:
                detail = response.text
            raise BackendError(str(detail), status_code=response.status_code)
        try:
            return response.json()
        except ValueError as exc:
            raise BackendError('Backend returned invalid JSON') from exc

    def products(self):
        return self._request('GET', '/products')['items']

    def save_draft(self, *, customer_id, order_id, items, customer_name, phone, delivery_address):
        return self._request('POST', '/orders/draft', json={
            'customer_id': customer_id, 'order_id': order_id, 'items': items,
            'customer_name': customer_name, 'phone': phone, 'delivery_address': delivery_address})

    def quote(self, order_id):
        return self._request('POST', f'/orders/{order_id}/quote')

    def confirm(self, *, order_id, customer_id, quote_version, confirmation_message_id):
        return self._request('POST', f'/orders/{order_id}/confirm', json={
            'customer_id': customer_id, 'quote_version': quote_version,
            'confirmation_message_id': confirmation_message_id})
