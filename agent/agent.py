"""MACOT conversation prototype. No database writes or order confirmations."""
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

import time
import random
from google.genai import errors

load_dotenv()

MENU = {"chocolate_chip": 2, "double_chocolate": 2, "red_velvet": 3,
        "kinder": 3, "nutella": 3, "lotus": 3}

class Item(BaseModel):
    flavor_id: str
    quantity: int = Field(ge=1)
    filling: str | None = None

class AgentOutput(BaseModel):
    reply: str
    language: str
    intent: str
    items: list[Item] = Field(default_factory=list)
    delivery_date: str | None = None
    customer_name: str | None = None
    phone: str | None = None
    delivery_address: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    ready_for_quote: bool = False
    customer_approved_quote: bool = False
    needs_human: bool = False

SYSTEM = """You are MACOT, a friendly cookie shop WhatsApp assistant in Lebanon.
Understand English, Arabic, Lebanese Arabic, Arabizi, and mixed language. Reply in the customer's language/style.
Menu (USD per cookie): chocolate_chip 2, double_chocolate 2, red_velvet 3, kinder 3, nutella 3, lotus 3.
Red velvet filling must be cream_cheese or white_chocolate. Never invent menu items, fees, delivery zones, capacity, or availability.
Customers choose a DELIVERY DATE ONLY, never a delivery time slot.
Extract information from the full conversation and retain already-provided details. Use canonical flavor IDs.
Resolve relative dates using the supplied current Lebanon date. If ambiguous, ask for clarification.
Ask for missing name, phone, delivery address, delivery date, items, quantities and red velvet filling when applicable. Ask concisely, grouping related questions naturally.
Do not say an order is confirmed. Do not claim a delivery date is available or quote a final total until backend tools validate it.
You may mention cookie subtotal from the menu, but delivery fee and final total are unknown.
Set ready_for_quote true only when all required order fields are present. customer_approved_quote must always be false in this prototype: no validated backend quote exists.
Set needs_human true when the customer requests the owner or you cannot resolve an important request.
Return structured data matching the schema. Missing unknown fields should be null, never fabricated.
"""

def main():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise SystemExit("Set GEMINI_API_KEY in .env first")
    client = genai.Client(api_key=key)
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    history = []
    print("MACOT agent prototype. Type 'exit' to quit. No orders are saved or confirmed.\n")
    while True:
        message = input("Customer: ").strip()
        if message.lower() in {"exit", "quit"}:
            break
        if not message:
            continue
        now = datetime.now(ZoneInfo("Asia/Beirut")).strftime("%Y-%m-%d %A")
        history.append({"role": "customer", "message": message})
        prompt = f"Current date in Lebanon: {now}\nConversation:\n{json.dumps(history, ensure_ascii=False)}\nReturn the current accumulated order state and a reply to the last message."
        try:
            max_attempts = 4

            for attempt in range(max_attempts):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM,
                            response_mime_type="application/json",
                            response_schema=AgentOutput,
                            temperature=0.2,
                        ),
                    )
                    break

                except errors.ServerError as exc:
                    if exc.code != 503:
                        raise

                    if attempt == max_attempts - 1:
                        raise

                    delay = min(2 ** attempt + random.uniform(0, 1), 10)
                    print(f"Gemini busy. Retrying in {delay:.1f}s...")
                    time.sleep(delay)

            output = AgentOutput.model_validate_json(response.text)

            history.append({
                "role": "assistant",
                "message": output.reply
            })

            print("MACOT:", output.reply)
            print(
                "STATE:",
                json.dumps(
                    output.model_dump(),
                    ensure_ascii=False,
                    indent=2
                ),
                "\n"
            )

        except Exception as exc:
            history.pop()
            print("API error:", exc)

if __name__ == "__main__":
    main()
