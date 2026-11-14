"""WhatsApp Cloud API webhook. Mount router in existing FastAPI backend."""
import hashlib
import hmac
import logging
import os
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
import httpx

router = APIRouter(prefix="/webhook/whatsapp", tags=["whatsapp"])
log = logging.getLogger(__name__)


def verify_signature(raw: bytes, signature: str | None) -> bool:
    secret = os.environ.get("WHATSAPP_APP_SECRET", "")
    if not secret or not signature or not signature.startswith("sha256="):
        return False
    digest = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature[7:], digest)


@router.get("")
async def verify_webhook(request: Request):
    params = request.query_params
    if (params.get("hub.mode") == "subscribe" and
        params.get("hub.verify_token") == os.getenv("WHATSAPP_VERIFY_TOKEN") and
        os.getenv("WHATSAPP_VERIFY_TOKEN")):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(status_code=403, detail="Invalid verification token")


async def handle_message(message: dict, sender: str):
    """MVP only. Production must persist/deduplicate message IDs before queueing."""
    if message.get("type") != "text":
        return
    message_id = message.get("id")
    text = message.get("text", {}).get("body", "")
    if not message_id or not text or not sender:
        return
    agent_url = os.getenv("AGENT_URL", "http://127.0.0.1:8000/agent/chat")
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            result = await client.post(agent_url, json={
                "customer_id": sender, "message_id": message_id, "message": text
            })
            result.raise_for_status()
            reply = result.json().get("reply")
            if reply:
                await send_whatsapp_reply(client, sender, reply)
    except Exception:
        log.exception("Failed to process WhatsApp message %s", message_id)


async def send_whatsapp_reply(client: httpx.AsyncClient, to: str, text: str):
    token = os.environ["WHATSAPP_ACCESS_TOKEN"]
    phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
    version = os.getenv("WHATSAPP_GRAPH_VERSION", "v23.0")
    url = f"https://graph.facebook.com/{version}/{phone_id}/messages"
    response = await client.post(url, headers={"Authorization": f"Bearer {token}"}, json={
        "messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}
    })
    response.raise_for_status()


@router.post("")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    raw = await request.body()
    if not verify_signature(raw, request.headers.get("x-hub-signature-256")):
        raise HTTPException(status_code=403, detail="Invalid signature")
    payload = await request.json()
    if payload.get("object") != "whatsapp_business_account":
        return {"ok": True}
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "messages":
                continue
            value = change.get("value", {})
            for message in value.get("messages", []):
                background_tasks.add_task(handle_message, message, message.get("from", ""))
    return {"ok": True}
