"""
Wompi API Client for payment processing.
Documentation: https://docs.wompi.co/
"""
import requests
import hashlib
import logging
from django.conf import settings
from typing import Dict, Optional

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
    
    def verify_event_signature(self, event_data: Dict, signature: str) -> bool:
        """
        Verify webhook event signature.
        
        Args:
            event_data: The event data from webhook
            signature: The signature from webhook headers
        
        Returns:
            True if signature is valid
        """
        try:
            # Wompi signature format: timestamp.signature
            timestamp, received_signature = signature.split('.')
            
            # Create signature string
            event_id = event_data.get('id', '')
            event_type = event_data.get('event', '')
            signature_string = f"{event_id}{event_type}{timestamp}"
            
            # Calculate expected signature
            expected_signature = hashlib.sha256(
                f"{signature_string}{self.events_secret}".encode()
            ).hexdigest()
            
            return expected_signature == received_signature
            
        except Exception as e:
            logger.error(f"Error verifying signature: {str(e)}")
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
