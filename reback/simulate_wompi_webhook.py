
import os
import sys
import django
import json

import hashlib
import requests
import uuid
from datetime import datetime

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from django.conf import settings
from reback.users.models import User

def generate_signature(event_id, event_type, timestamp, secret):
    """Generates the Wompi signature."""
    signature_string = f"{event_id}{event_type}{timestamp}"
    return hashlib.sha256(f"{signature_string}{secret}".encode()).hexdigest()

def simulate_approved_payment(user_email, plan_tier='premium', amount_in_cents=100000):
    """Simulates an APPROVED transaction webhook from Wompi."""
    
    try:
        user = User.objects.get(email=user_email)
        print(f"✅ User found: {user.email} (ID: {user.id})")
    except User.DoesNotExist:
        print(f"❌ User with email {user_email} not found.")
        return

    # Generate unique IDs
    transaction_id = f"tr_test_{uuid.uuid4().hex[:10]}"
    reference = f"sub-{plan_tier}-{user.id}-{datetime.now().timestamp()}"
    event_id = f"evt_test_{uuid.uuid4().hex[:10]}"
    timestamp = str(int(datetime.now().timestamp()))
    event_type = "transaction.updated"

    # 1. Construct the Payload (mimicking Wompi structure)
    payload = {
        "event": event_type,
        "data": {
            "transaction": {
                "id": transaction_id,
                "amount_in_cents": amount_in_cents,
                "reference": reference,
                "customer_email": user.email,
                "currency": "COP",
                "payment_method_type": "CARD",
                "status": "APPROVED",
                "status_message": "Aprobada",
                "payment_method": {
                    "type": "CARD",
                    "extra": {
                        "name": "VI",
                        "brand": "VISA",
                        "last_four": "4242"
                    },
                    "payment_source_id": f"src_{uuid.uuid4().hex[:10]}" # Token for recurring
                }
            }
        },
        "environment": "test",
        "signature": {
            "checksum": "legacy_checksum_ignored_by_your_view",
            "properties": ["transaction.id", "transaction.status", "transaction.amount_in_cents"]
        },
        "timestamp": int(timestamp),
        "sent_at": datetime.now().isoformat(),
        "id": event_id
    }

    # 2. Generate Signature Header
    # Wompi sends signature in header X-Event-Signature: timestamp.checksum
    signature_hash = generate_signature(event_id, event_type, timestamp, "test_events_pAgyO90vXNik4WKEpTHdifl2lRmWIsC2")
    header_signature = f"{timestamp}.{signature_hash}"

    print(f"\n🚀 Sending Webhook to localhost...")
    print(f"Payload Reference: {reference}")
    print(f"Signature Header: {header_signature}")

    # 3. Send POST request
    url = "http://localhost:8000/payments/wompi/webhook/"
    headers = {
        "Content-Type": "application/json",
        "HTTP_X_EVENT_SIGNATURE": header_signature # Django converts X-Header to HTTP_X_HEADER
    }
    
    # Note: requests library uses 'X-Event-Signature', Django sees 'HTTP_X_EVENT_SIGNATURE'
    # We send standard header.
    requests_headers = {
        "Content-Type": "application/json",
        "X-Event-Signature": header_signature
    }

    try:
        response = requests.post(url, json=payload, headers=requests_headers)
        print(f"\n📡 Response Status: {response.status_code}")
        print(f"Response Body: {response.text}")

        if response.status_code == 200:
            print("\n✅ Webhook processed successfully!")
            print("👉 Check the Django Admin or Database to verify the subscription is active.")
        else:
            print("\n❌ Webhook failed.")
    except Exception as e:
        print(f"\n❌ Request failed: {e}")
        print("Make sure the Django server is running on port 8000.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python simulate_wompi_webhook.py <user_email>")
        print("Example: python simulate_wompi_webhook.py tu_email@ejemplo.com")
    else:
        simulate_approved_payment(sys.argv[1])
