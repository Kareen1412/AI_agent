"""Set a real, shop-approved flat delivery fee without resetting any other data.
Usage (from backend/): python set_delivery_fee.py 3.00
"""
import sys
from decimal import Decimal, InvalidOperation
from firebase_client import db

if len(sys.argv) != 2:
    raise SystemExit('Usage: python set_delivery_fee.py <actual_USD_fee>')
try:
    fee = Decimal(sys.argv[1])
except InvalidOperation:
    raise SystemExit('Invalid delivery fee')
if not fee.is_finite() or fee < 0:
    raise SystemExit('Delivery fee must be a nonnegative number')
db.collection('shop_settings').document('config').set(
    {'delivery_fees': {'flat': float(fee)}}, merge=True)
print(f'Configured flat delivery fee: ${fee:.2f} USD')
