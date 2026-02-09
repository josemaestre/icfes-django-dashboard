"""
Wompi payment integration views.
Handles checkout, webhooks, and subscription management.
"""
import json
import logging
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.urls import reverse
from django.utils import timezone

from reback.users.models import User
from reback.users.subscription_models import SubscriptionPlan, UserSubscription
from reback.users.wompi_client import wompi_client

logger = logging.getLogger(__name__)


@login_required
def wompi_checkout(request):
    """
    Display Wompi checkout page with widget.
    """
    plan_tier = request.GET.get('plan', 'basic')
    
    try:
        plan = get_object_or_404(SubscriptionPlan, tier=plan_tier, is_active=True)
        
        # Free plan doesn't need payment
        if plan.tier == 'free':
            return redirect('pages:pricing')
        
        # Generate unique reference (Use int timestamp to avoid float precision issues)
        reference = f"sub-{plan.tier}-{request.user.id}-{int(timezone.now().timestamp())}"
        
        # Amount in cents
        amount_in_cents = int(float(plan.price_monthly) * 100)
        
        # Get Public Key from settings
        public_key = settings.WOMPI_PUBLIC_KEY
        
        # Get Integrity Secret from settings
        # Note: Use WOMPI_EVENTS_SECRET if WOMPI_INTEGRITY_SECRET doesn't work
        integrity_secret = settings.WOMPI_EVENTS_SECRET or settings.WOMPI_INTEGRITY_SECRET
        
        # Generate Signature: SHA256(Reference + AmountInCents + Currency + IntegritySecret)
        import hashlib
        signature_source = f"{reference}{amount_in_cents}COP{integrity_secret}"
        integrity_signature = hashlib.sha256(signature_source.encode('utf-8')).hexdigest()
        
        # LOGS DETALLADOS SOLICITADOS POR EL USUARIO
        print("="*50)
        print("DEBUG WOMPI PARAMETERS (TRYING EVENTS SECRET):")
        print(f"Reference: {reference}")
        print(f"Amount (Cents): {amount_in_cents}")
        print(f"Currency: COP")
        print(f"Integrity Secret (Events): {integrity_secret}")
        print(f"Public Key: {public_key}")
        print(f"Signature Source (Concatenation): {signature_source}")
        print(f"Generated Signature: {integrity_signature}")
        print("="*50)
        
        context = {
            'plan': plan,
            'reference': reference,
            'amount_in_cents': amount_in_cents,
            'integrity_signature': integrity_signature, # NEW
            'customer_email': request.user.email,
            'wompi_public_key': public_key,
            'success_url': request.build_absolute_uri(reverse('payments:wompi_success')),
            'cancel_url': request.build_absolute_uri(reverse('payments:cancel')),
        }
        
        return render(request, 'payments/wompi_checkout.html', context)
        
    except SubscriptionPlan.DoesNotExist:
        return redirect('pages:pricing')


@csrf_exempt
@require_POST
def wompi_webhook(request):
    """
    Handle Wompi webhook events.
    
    Events:
    - transaction.updated: Payment status changed
    """
    try:
        # Get signature from headers
        signature = request.META.get('HTTP_X_EVENT_SIGNATURE', '')
        
        # Parse event data
        event_data = json.loads(request.body)
        
        # Verify signature
        if not wompi_client.verify_event_signature(event_data, signature):
            logger.warning("Invalid webhook signature")
            return HttpResponse(status=401)
        
        # Handle event
        event_type = event_data.get('event')
        
        if event_type == 'transaction.updated':
            handle_transaction_updated(event_data['data']['transaction'])
        
        return HttpResponse(status=200)
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return HttpResponse(status=500)


def handle_transaction_updated(transaction):
    """Handle transaction status update."""
    try:
        status = transaction['status']
        reference = transaction['reference']
        
        # Extract user_id and plan_tier from reference
        # Format: "sub-{tier}-{user_id}-{timestamp}"
        parts = reference.split('-')
        if len(parts) < 3 or parts[0] != 'sub':
            logger.warning(f"Invalid reference format: {reference}")
            return
        
        plan_tier = parts[1]
        user_id = int(parts[2])
        
        if status == 'APPROVED':
            # Payment successful, activate subscription
            user = User.objects.get(id=user_id)
            plan = SubscriptionPlan.objects.get(tier=plan_tier)
            
            # Get payment source ID for recurring payments
            payment_source_id = transaction.get('payment_method', {}).get('payment_source_id', '')
            
            # Create or update subscription
            subscription, created = UserSubscription.objects.update_or_create(
                user=user,
                defaults={
                    'plan': plan,
                    'wompi_subscription_id': transaction['id'],
                    'wompi_payment_method_id': payment_source_id,
                    'is_active': True,
                    'start_date': timezone.now(),
                }
            )
            
            logger.info(f"Subscription {'created' if created else 'updated'} for user {user.email}")
            
        elif status == 'DECLINED' or status == 'ERROR':
            logger.warning(f"Transaction {transaction['id']} failed with status: {status}")
            
    except Exception as e:
        logger.error(f"Error handling transaction update: {str(e)}")


@login_required
def wompi_success(request):
    """Display success page after Wompi payment."""
    transaction_id = request.GET.get('id')
    
    context = {
        'transaction_id': transaction_id,
        'title': '¡Pago Exitoso!',
        'message': 'Tu suscripción ha sido activada correctamente.',
    }
    
    return render(request, 'payments/success.html', context)
