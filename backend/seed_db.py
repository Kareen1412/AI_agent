
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone

# ============================================
# FIREBASE CONNECTION
# ============================================

cred = credentials.Certificate("serviceAccountKey.json")

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()

NOW = datetime.now(timezone.utc)

# ============================================
# 1. MENU COLLECTION
# ============================================

menu = {
    "chocolate_chip": {
        "flavor_id": "chocolate_chip",
        "name": "Chocolate Chip",
        "price": 2,
        "currency": "USD",
        "available": True,
        "fillings": []
    },
    "double_chocolate": {
        "flavor_id": "double_chocolate",
        "name": "Double Chocolate",
        "price": 2,
        "currency": "USD",
        "available": True,
        "fillings": []
    },
    "red_velvet": {
        "flavor_id": "red_velvet",
        "name": "Red Velvet",
        "price": 3,
        "currency": "USD",
        "available": True,
        "fillings": ["cream_cheese", "white_chocolate"]
    },
    "kinder": {
        "flavor_id": "kinder",
        "name": "Kinder",
        "price": 3,
        "currency": "USD",
        "available": True,
        "fillings": []
    },
    "nutella": {
        "flavor_id": "nutella",
        "name": "Nutella",
        "price": 3,
        "currency": "USD",
        "available": True,
        "fillings": []
    },
    "lotus": {
        "flavor_id": "lotus",
        "name": "Lotus",
        "price": 3,
        "currency": "USD",
        "available": True,
        "fillings": []
    }
}

for flavor_id, data in menu.items():
    db.collection("menu").document(flavor_id).set(data)

print("✓ Menu created")

# ============================================
# 2. PRODUCTION WEEKS
# ============================================

production_weeks = {
    "2026-11-23": {
        "week_id": "2026-11-23",
        "production_start_date": "2026-11-21",
        "production_end_date": "2026-11-22",
        "delivery_start_date": "2026-11-23",
        "delivery_end_date": "2026-11-29",
        "max_cookies": 100,
        "reserved_cookies": 0,
        "confirmed_orders": 0,
        "enabled": True,
        "created_at": NOW,
        "updated_at": NOW
    },
    "2026-11-30": {
        "week_id": "2026-11-30",
        "production_start_date": "2026-11-28",
        "production_end_date": "2026-11-29",
        "delivery_start_date": "2026-11-30",
        "delivery_end_date": "2026-12-06",
        "max_cookies": 100,
        "reserved_cookies": 0,
        "confirmed_orders": 0,
        "enabled": True,
        "created_at": NOW,
        "updated_at": NOW
    }
}

for week_id, data in production_weeks.items():
    db.collection("production_weeks").document(week_id).set(data)

print("✓ Production weeks created")

# ============================================
# 3. CUSTOMERS
# ============================================

customer = {
    "customer_id": "96170123456",
    "name": "Sara",
    "phone": "96170123456",
    "default_address": "Jounieh, Lebanon",
    "preferred_language": "arabizi",
    "created_at": NOW,
    "updated_at": NOW
}

db.collection("customers").document(
    customer["customer_id"]
).set(customer)

print("✓ Sample customer created")

# ============================================
# 4. ORDERS
# ============================================

order = {
    "order_id": "CK-001",
    "customer_id": "96170123456",
    "customer_name": "Sara",
    "phone": "96170123456",
    "items": [
        {
            "flavor_id": "kinder",
            "quantity": 3,
            "filling": None,
            "unit_price": 3,
            "subtotal": 9
        },
        {
            "flavor_id": "lotus",
            "quantity": 2,
            "filling": None,
            "unit_price": 3,
            "subtotal": 6
        }
    ],
    "total_cookies": 5,
    "delivery_date": "2026-11-25",
    "production_week_id": "2026-11-23",
    "delivery_address": "Jounieh, Lebanon",
    "delivery_type": "delivery",
    "subtotal": 15,
    "delivery_fee": 3,
    "total": 18,
    "currency": "USD",
    "status": "draft",
    "capacity_reserved": False,
    "quote_version": 0,
    "quoted_at": None,
    "confirmed_at": None,
    "created_at": NOW,
    "updated_at": NOW
}

db.collection("orders").document("CK-001").set(order)

print("✓ Sample draft order created")

# ============================================
# 5. CONVERSATIONS
# ============================================

conversation = {
    "customer_id": "96170123456",
    "active_order_id": "CK-001",
    "state": "collecting_details",
    "last_message_at": NOW
}

conversation_ref = db.collection("conversations").document(
    "96170123456"
)

conversation_ref.set(conversation)

conversation_ref.collection("messages").document(
    "test-message-001"
).set({
    "message_id": "test-message-001",
    "role": "customer",
    "content": "bade 3 kinder w 2 lotus",
    "language": "arabizi",
    "created_at": NOW
})

print("✓ Sample conversation and message created")

# ============================================
# 6. PROCESSED MESSAGES
# ============================================

db.collection("processed_messages").document(
    "test-message-001"
).set({
    "message_id": "test-message-001",
    "customer_id": "96170123456",
    "status": "processed",
    "received_at": NOW,
    "processed_at": NOW
})

print("✓ Sample processed message created")

# ============================================
# 7. SHOP SETTINGS
# ============================================

settings = {
    "shop_name": "MACOT",
    "currency": "USD",
    "timezone": "Asia/Beirut",
    "accepting_orders": True,
    "delivery_enabled": True,
    "pickup_enabled": False,
    "minimum_order_quantity": 1,
    "minimum_notice_hours": 24,
    "production_days": ["saturday", "sunday"],
    "delivery_week_start": "monday",
    "default_weekly_cookie_limit": 100,
    "delivery_areas": [],
    "delivery_fees": {},
    "automatic_confirmation": True
}

db.collection("shop_settings").document("config").set(settings)

print("✓ Shop settings created")

# ============================================
# 8. ORDER COUNTER
# ============================================

db.collection("counters").document("orders").set({
    "last_number": 1
})

print("✓ Order counter created")

print("\nMACOT Firestore database initialized successfully!")
