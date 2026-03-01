"""
Wompi API Client for payment processing.
Documentation: https://docs.wompi.co/
"""
import hashlib
import logging
from typing import Dict, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class WompiClient:
    """Client for Wompi API interactions."""
    
    def __init__(self):
        self.base_url = settings.WOMPI_BASE_URL
        self.public_key = settings.WOMPI_PUBLIC_KEY
        self.private_key = settings.WOMPI_PRIVATE_KEY
        self.events_secret = settings.WOMPI_EVENTS_SECRET
    
    def get_acceptance_token(self) -> Optional[str]:
        """
        Get acceptance token for terms and conditions.
        Required before creating transactions.
        """
        try:
            url = f"{self.base_url}/merchants/{self.public_key}"
            response = requests.get(url)
            response.raise_for_status()
            
            data = response.json()
            presigned_acceptance = data['data']['presigned_acceptance']
            return presigned_acceptance['acceptance_token']
            
        except Exception as e:
            logger.error(f"Error getting acceptance token: {str(e)}")
            return None
    
    def create_transaction(
        self,
        amount_in_cents: int,
        currency: str,
        customer_email: str,
        reference: str,
        payment_method_type: str = "CARD",
        payment_source_id: Optional[str] = None,
        redirect_url: Optional[str] = None
    ) -> Dict:
        """
        Create a transaction in Wompi.
        
        Args:
            amount_in_cents: Amount in cents (e.g., 100000 = $1,000 COP)
            currency: Currency code (COP)
            customer_email: Customer email
            reference: Unique reference for this transaction
            payment_method_type: CARD, NEQUI, PSE
            payment_source_id: For recurring payments (tokenized card)
            redirect_url: URL to redirect after payment
        
        Returns:
            Dict with transaction data or error
        """
        try:
            url = f"{self.base_url}/transactions"
            
            acceptance_token = self.get_acceptance_token()
            if not acceptance_token:
                return {"error": "Could not get acceptance token"}
            
            payload = {
                "acceptance_token": acceptance_token,
                "amount_in_cents": amount_in_cents,
                "currency": currency,
                "customer_email": customer_email,
                "reference": reference,
                "payment_method": {
                    "type": payment_method_type,
                }
            }
            
            # For recurring payments with saved card
            if payment_source_id:
                payload["payment_method"]["payment_source_id"] = payment_source_id
            
            # Add redirect URL if provided
            if redirect_url:
                payload["redirect_url"] = redirect_url
            
            headers = {
                "Authorization": f"Bearer {self.private_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating transaction: {str(e)}")
            return {"error": str(e)}
    
    def get_transaction(self, transaction_id: str) -> Dict:
        """Get transaction details by ID."""
        try:
            url = f"{self.base_url}/transactions/{transaction_id}"
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting transaction: {str(e)}")
            return {"error": str(e)}
    
    def _get_property_value(self, data: Dict, property_path: str) -> str:
        """Resolve a dotted property path inside event data."""
        def snake_to_camel(value: str) -> str:
            parts = value.split("_")
            return parts[0] + "".join(p.capitalize() for p in parts[1:])

        def camel_to_snake(value: str) -> str:
            out = []
            for ch in value:
                if ch.isupper():
                    out.append("_")
                    out.append(ch.lower())
                else:
                    out.append(ch)
            return "".join(out).lstrip("_")

        current = data
        for key in property_path.split('.'):
            if isinstance(current, dict) and key in current:
                current = current[key]
                continue

            # Compatibility for occasional camelCase/snake_case differences
            alt_keys = [snake_to_camel(key), camel_to_snake(key)]
            matched = False
            for alt_key in alt_keys:
                if isinstance(current, dict) and alt_key in current:
                    current = current[alt_key]
                    matched = True
                    break
            if matched:
                continue

            return ""

        return "" if current is None else str(current)

    def verify_event_signature(self, event_data: Dict, checksum: str) -> bool:
        """
        Verify webhook checksum using Wompi official algorithm.
        
        Args:
            event_data: The event data from webhook
            checksum: The checksum from X-Event-Checksum header or body signature.checksum
        
        Returns:
            True if checksum is valid
        """
        try:
            if not checksum:
                return False

            signature = event_data.get("signature", {}) or {}
            properties = signature.get("properties", []) or []
            timestamp = event_data.get("timestamp", "")
            data = event_data.get("data", {}) or {}

            if not properties or timestamp == "":
                return False

            values = "".join(self._get_property_value(data, prop) for prop in properties)
            payload_to_sign = f"{values}{timestamp}{self.events_secret}"
            expected_checksum = hashlib.sha256(payload_to_sign.encode("utf-8")).hexdigest()

            return expected_checksum.lower() == checksum.lower()
            
        except Exception as e:
            logger.error(f"Error verifying webhook checksum: {str(e)}")
            return False
    
    def tokenize_card(
        self,
        card_number: str,
        cvc: str,
        exp_month: str,
        exp_year: str,
        card_holder: str
    ) -> Dict:
        """
        Tokenize a credit card for recurring payments.
        
        Returns:
            Dict with payment_source_id or error
        """
        try:
            url = f"{self.base_url}/payment_sources"
            
            acceptance_token = self.get_acceptance_token()
            if not acceptance_token:
                return {"error": "Could not get acceptance token"}
            
            payload = {
                "type": "CARD",
                "token": {
                    "card_number": card_number,
                    "cvc": cvc,
                    "exp_month": exp_month,
                    "exp_year": exp_year,
                    "card_holder": card_holder
                },
                "acceptance_token": acceptance_token
            }
            
            headers = {
                "Authorization": f"Bearer {self.public_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error tokenizing card: {str(e)}")
            return {"error": str(e)}


# Singleton instance
wompi_client = WompiClient()
