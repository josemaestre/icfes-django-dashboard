"""
Wompi payment integration views.
Handles checkout, webhooks, and subscription management.
"""
import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
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
        
        # Amount in cents (deterministic rounding for signature stability)
        amount_in_cents = int(
            (Decimal(plan.price_monthly) * Decimal("100")).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        
        # Get Public Key from settings
        public_key = settings.WOMPI_PUBLIC_KEY
        
        # Get Integrity Secret from settings
        # IMPORTANT: Use WOMPI_INTEGRITY_SECRET for widget signature
        # WOMPI_EVENTS_SECRET is ONLY for webhook verification
        integrity_secret = settings.WOMPI_INTEGRITY_SECRET
        
        # Generate Signature: SHA256(Reference + AmountInCents + Currency + IntegritySecret)
        import hashlib
        signature_source = f"{reference}{amount_in_cents}COP{integrity_secret}"
        integrity_signature = hashlib.sha256(signature_source.encode('utf-8')).hexdigest()
        
        if settings.PAYMENTS_DEBUG_LOGS:
            logger.info("="*50)
            logger.info("WOMPI CHECKOUT PARAMETERS:")
            logger.info("Reference: %s", reference)
            logger.info("Amount (Cents): %s", amount_in_cents)
            logger.info("Currency: COP")
            logger.info("Public Key Prefix: %s", public_key[:12])
            logger.info("Generated Signature Prefix: %s", integrity_signature[:12])
            logger.info("="*50)
        
        context = {
            'plan': plan,
            'reference': reference,
            'amount_in_cents': amount_in_cents,
            'integrity_signature': integrity_signature, # NEW
            'customer_email': request.user.email,
            'wompi_public_key': public_key,
            'success_url': request.build_absolute_uri(reverse('payments:wompi_success')),
            'cancel_url': request.build_absolute_uri(reverse('payments:cancel')),
            'user_type_choices': User.USER_TYPE_CHOICES,
            'payments_debug_logs': settings.PAYMENTS_DEBUG_LOGS,
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
        # Parse event data
        event_data = json.loads(request.body)

        # Official Wompi checksum header. Keep fallback to body for local tests.
        checksum = request.META.get('HTTP_X_EVENT_CHECKSUM', '')
        if not checksum:
            checksum = (event_data.get('signature', {}) or {}).get('checksum', '')
        
        # Verify checksum
        if not wompi_client.verify_event_signature(event_data, checksum):
            logger.warning("Invalid webhook checksum")
            return HttpResponse(status=401)
        
        # Handle event
        event_type = event_data.get('event')

        if settings.PAYMENTS_DEBUG_LOGS and event_type == 'transaction.updated':
            tx = (event_data.get('data', {}) or {}).get('transaction', {}) or {}
            logger.info("WOMPI TX KEYS: %s", list(tx.keys()))
            logger.info("WOMPI payment_method: %s", tx.get('payment_method'))
            logger.info("WOMPI payment_link: %s", tx.get('payment_link'))
        
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
            
            # Get payment source ID for recurring payments (robust paths)
            payment_method = transaction.get('payment_method') or {}
            payment_link = transaction.get('payment_link') or {}
            payment_source_id = (
                payment_method.get('payment_source_id')
                or payment_link.get('payment_source_id')
                or ''
            )

            existing = UserSubscription.objects.filter(user=user).first()
            fallback_payment_source_id = (
                existing.wompi_payment_method_id if existing else ''
            )
            
            # Create or update subscription
            subscription, created = UserSubscription.objects.update_or_create(
                user=user,
                defaults={
                    'plan': plan,
                    'wompi_subscription_id': transaction['id'],
                    # Do not overwrite a previously saved source id with empty value
                    'wompi_payment_method_id': payment_source_id or fallback_payment_source_id,
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
    
    # Save user_type and organization_name if provided
    user_type = request.GET.get('user_type', '')
    organization_name = request.GET.get('organization_name', '')
    
    if user_type:
        request.user.user_type = user_type
        if organization_name:
            request.user.organization_name = organization_name
        request.user.save()
        logger.info(f"Updated user {request.user.email} with user_type: {user_type}")
    
    context = {
        'transaction_id': transaction_id,
        'title': '¡Pago Exitoso!',
        'message': 'Tu suscripción ha sido activada correctamente.',
    }
    
    return render(request, 'payments/success.html', context)
