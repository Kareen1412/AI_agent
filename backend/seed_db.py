
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

db.collection("shop_settings").document("config").update({
    "delivery_fees": {"flat": 3}
})