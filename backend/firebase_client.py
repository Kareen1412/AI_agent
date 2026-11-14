"""Firestore connection for MACOT. Never commit serviceAccountKey.json."""
import os
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore


def get_db():
    if not firebase_admin._apps:
        key = os.getenv('FIREBASE_SERVICE_ACCOUNT')
        if not key:
            key = str(Path(__file__).resolve().parent / 'serviceAccountKey.json')
        if Path(key).is_file():
            firebase_admin.initialize_app(credentials.Certificate(key))
        else:
            firebase_admin.initialize_app()  # Application Default Credentials
    return firestore.client()


db = get_db()
