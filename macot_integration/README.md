# MACOT — WhatsApp + Owner Dashboard

This is **Person 3's integration starter**, designed to work with Person 1's `/agent/chat` and Person 2's order/menu/capacity API. It does not include those services or Firestore.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` with Meta credentials and a shared backend admin token. Never commit `.env`.

## WhatsApp webhook

In Person 2's existing FastAPI `main.py`:

```python
from whatsapp.webhook import router as whatsapp_router
app.include_router(whatsapp_router)
```

Run the existing FastAPI server (typically `uvicorn backend.main:app --reload --port 8000` from the repository root). Expose port 8000 through an HTTPS tunnel. Set Meta callback URL to `https://YOUR_PUBLIC_DOMAIN/webhook/whatsapp`, and verify token to the value in `.env`. Subscribe to `messages` events.

**Note:** Meta requires an app, WhatsApp Cloud API configuration, appropriate permissions, a phone number ID and token. Test numbers may require adding approved recipients. Cloud API customer service window/template restrictions apply.

## Dashboard

```bash
streamlit run dashboard/app.py
```

Dashboard uses Person 2's `/orders`, `/availability`, `/delivery-capacity/{date}`, and `/menu` endpoints. It assumes an `Authorization: Bearer <ADMIN_API_TOKEN>` header and specific response shapes from the shared contract. Coordinate authentication and endpoint behavior with Person 2.

## Production gaps (important)

- Persist incoming WhatsApp message IDs and deduplicate **before** enqueueing or processing. Meta may retry webhook events.
- Replace FastAPI in-process background tasks with a durable queue for production; order events per customer and implement retry/dead-letter behavior.
- Authenticate the agent endpoint separately from public WhatsApp requests; verify sender/order ownership.
- Add login and authorization to dashboard; shared static bearer token is only a local MVP boundary.
- Add monitoring and a reliable reply delivery/retry policy.
- Never allow direct Firestore edits from the dashboard client; enforce capacity/status transitions server-side.
