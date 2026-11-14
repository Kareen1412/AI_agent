
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

"""Seed MACOT as an online clothing store.

Run from the backend directory: python seed_clothing_db.py
Requires backend/serviceAccountKey.json and firebase-admin.

WARNING: Deletes the old cookie-specific `menu` and `production_weeks`
collections. Existing orders are NOT deleted or migrated.
"""
from datetime import datetime, timezone
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore

BASE = Path(__file__).resolve().parent
KEY = BASE / 'serviceAccountKey.json'
if not KEY.exists():
    raise FileNotFoundError(f'Missing Firebase service account: {KEY}')
if not firebase_admin._apps:
    firebase_admin.initialize_app(credentials.Certificate(str(KEY)))
db = firestore.client()
NOW = datetime.now(timezone.utc)

# Each variant is a size/color combination with its own inventory.
products = {
    'basic_tshirt': {
        'product_id': 'basic_tshirt', 'name': 'Basic Cotton T-Shirt',
        'description': 'Everyday crew-neck cotton T-shirt',
        'category': 'tops', 'price': 15, 'currency': 'USD',
        'available': True, 'image_urls': [],
        'variants': [
            {'sku': 'TSH-BLK-S', 'size': 'S', 'color': 'Black', 'stock': 10},
            {'sku': 'TSH-BLK-M', 'size': 'M', 'color': 'Black', 'stock': 12},
            {'sku': 'TSH-BLK-L', 'size': 'L', 'color': 'Black', 'stock': 8},
            {'sku': 'TSH-WHT-M', 'size': 'M', 'color': 'White', 'stock': 10},
        ],
    },
    'oversized_hoodie': {
        'product_id': 'oversized_hoodie', 'name': 'Oversized Hoodie',
        'description': 'Relaxed-fit pullover hoodie',
        'category': 'hoodies', 'price': 35, 'currency': 'USD',
        'available': True, 'image_urls': [],
        'variants': [
            {'sku': 'HOD-GRY-S', 'size': 'S', 'color': 'Grey', 'stock': 6},
            {'sku': 'HOD-GRY-M', 'size': 'M', 'color': 'Grey', 'stock': 8},
            {'sku': 'HOD-GRY-L', 'size': 'L', 'color': 'Grey', 'stock': 5},
            {'sku': 'HOD-BLK-M', 'size': 'M', 'color': 'Black', 'stock': 7},
        ],
    },
    'straight_jeans': {
        'product_id': 'straight_jeans', 'name': 'Straight-Leg Jeans',
        'description': 'Classic straight-leg denim jeans',
        'category': 'bottoms', 'price': 40, 'currency': 'USD',
        'available': True, 'image_urls': [],
        'variants': [
            {'sku': 'JNS-BLU-28', 'size': '28', 'color': 'Blue', 'stock': 4},
            {'sku': 'JNS-BLU-30', 'size': '30', 'color': 'Blue', 'stock': 7},
            {'sku': 'JNS-BLU-32', 'size': '32', 'color': 'Blue', 'stock': 6},
            {'sku': 'JNS-BLK-30', 'size': '30', 'color': 'Black', 'stock': 5},
        ],
    },
    'summer_dress': {
        'product_id': 'summer_dress', 'name': 'Summer Midi Dress',
        'description': 'Lightweight casual midi dress',
        'category': 'dresses', 'price': 30, 'currency': 'USD',
        'available': True, 'image_urls': [],
        'variants': [
            {'sku': 'DRS-BGE-S', 'size': 'S', 'color': 'Beige', 'stock': 5},
            {'sku': 'DRS-BGE-M', 'size': 'M', 'color': 'Beige', 'stock': 7},
            {'sku': 'DRS-BGE-L', 'size': 'L', 'color': 'Beige', 'stock': 3},
        ],
    },
}

for product_id, product in products.items():
    db.collection('products').document(product_id).set({
        **product, 'created_at': NOW, 'updated_at': NOW
    }, merge=True)
print(f'✓ {len(products)} clothing products created')

customer = {
    'customer_id': '96170123456', 'name': 'Sara', 'phone': '96170123456',
    'default_address': 'Jounieh, Lebanon', 'preferred_language': 'arabizi',
    'created_at': NOW, 'updated_at': NOW,
}
db.collection('customers').document(customer['customer_id']).set(customer, merge=True)
print('✓ Sample customer created')

# Sample draft order; stock is not reserved until confirmed by backend transaction.
order = {
    'order_id': 'CL-001', 'customer_id': '96170123456',
    'customer_name': 'Sara', 'phone': '96170123456',
    'items': [
        {'product_id': 'basic_tshirt', 'product_name': 'Basic Cotton T-Shirt',
         'sku': 'TSH-BLK-M', 'size': 'M', 'color': 'Black', 'quantity': 2,
         'unit_price': 15, 'subtotal': 30},
        {'product_id': 'oversized_hoodie', 'product_name': 'Oversized Hoodie',
         'sku': 'HOD-GRY-S', 'size': 'S', 'color': 'Grey', 'quantity': 1,
         'unit_price': 35, 'subtotal': 35},
    ],
    'total_items': 3, 'delivery_address': 'Jounieh, Lebanon',
    'delivery_type': 'delivery', 'subtotal': 65, 'delivery_fee': 3,
    'total': 68, 'currency': 'USD', 'status': 'draft',
    'inventory_reserved': False, 'quote_version': 0, 'quoted_at': None,
    'confirmed_at': None, 'created_at': NOW, 'updated_at': NOW,
}
db.collection('orders').document('CL-001').set(order)
print('✓ Sample clothing order created')

conversation_ref = db.collection('conversations').document('96170123456')
conversation_ref.set({
    'customer_id': '96170123456', 'active_order_id': 'CL-001',
    'state': 'collecting_details', 'last_message_at': NOW,
}, merge=True)
conversation_ref.collection('messages').document('clothing-test-message-001').set({
    'message_id': 'clothing-test-message-001', 'role': 'customer',
    'content': 'bade 2 black tshirts size M w grey hoodie size S',
    'language': 'arabizi', 'created_at': NOW,
})
print('✓ Sample conversation created')

db.collection('processed_messages').document('clothing-test-message-001').set({
    'message_id': 'clothing-test-message-001',
    'customer_id': '96170123456', 'status': 'processed',
    'received_at': NOW, 'processed_at': NOW,
})
print('✓ Sample processed message created')

settings = {
    'shop_name': 'MACOT', 'shop_type': 'clothing',
    'currency': 'USD', 'timezone': 'Asia/Beirut',
    'accepting_orders': True, 'delivery_enabled': True,
    'pickup_enabled': False, 'minimum_order_quantity': 1,
    'delivery_areas': [], 'delivery_fees': {},
    'automatic_confirmation': True, 'inventory_tracking': True,
    'require_size_selection': True, 'require_color_selection': True,
    'updated_at': NOW,
}
# Overwrite settings to remove old cookie-specific scheduling fields.
db.collection('shop_settings').document('config').set(settings)
print('✓ Clothing shop settings created')

db.collection('counters').document('clothing_orders').set({'last_number': 1}, merge=True)
print('✓ Clothing order counter created')

# Delete cookie-only collections, in safe Firestore batches.
def delete_collection(name: str, batch_size: int = 200):
    collection = db.collection(name)
    removed = 0
    while True:
        docs = list(collection.limit(batch_size).stream())
        if not docs:
            break
        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()
        removed += len(docs)
    print(f'✓ Deleted {removed} documents from old {name} collection')

for old_collection in ('menu', 'production_weeks'):
    delete_collection(old_collection)

print('\nMACOT clothing store Firestore seed complete!')
print('NOTE: Existing cookie orders and conversations are not migrated or deleted.')
print('NOTE: Update FastAPI endpoints, agent prompts, and inventory transactions before taking real orders.')
