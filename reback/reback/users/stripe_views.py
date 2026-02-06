"""
Stripe payment integration views.
Handles checkout sessions, webhooks, and subscription management.
"""
import stripe
import logging
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.urls import reverse

from reback.users.models import User
from reback.users.subscription_models import SubscriptionPlan, UserSubscription

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


@login_required
@require_POST
def create_checkout_session(request):
    """
    Create a Stripe Checkout Session for subscription payment.
    
    Expected POST data:
    - plan_tier: 'basic', 'premium', or 'enterprise'
    """
    try:
        plan_tier = request.POST.get('plan_tier')
        
        # Get the subscription plan
        plan = get_object_or_404(SubscriptionPlan, tier=plan_tier, is_active=True)
        
        # Free plan doesn't need checkout
        if plan.tier == 'free':
            return JsonResponse({'error': 'Free plan does not require payment'}, status=400)
        
        # Get or create Stripe customer
        user = request.user
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.name if hasattr(user, 'name') else user.email,
                metadata={'user_id': user.id}
            )
            user.stripe_customer_id = customer.id
            user.save(update_fields=['stripe_customer_id'])
        else:
            customer_id = user.stripe_customer_id
        
        # Create Checkout Session
        # Note: You need to create Products and Prices in Stripe Dashboard first
        # For now, we'll use price_data (creates price on the fly)
        checkout_session = stripe.checkout.Session.create(
            customer=user.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': plan.name,
                        'description': plan.description,
                    },
                    'unit_amount': int(float(plan.price_monthly) * 100),  # Convert to cents
                    'recurring': {
                        'interval': 'month',
                    },
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=request.build_absolute_uri(reverse('payments:success')) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.build_absolute_uri(reverse('payments:cancel')),
            metadata={
                'user_id': user.id,
                'plan_tier': plan.tier,
            }
        )
        
        return JsonResponse({'sessionId': checkout_session.id})
        
    except SubscriptionPlan.DoesNotExist:
        return JsonResponse({'error': 'Invalid plan selected'}, status=400)
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Handle Stripe webhook events.
    
    Events handled:
    - checkout.session.completed: Activate subscription
    - customer.subscription.updated: Update subscription
    - customer.subscription.deleted: Cancel subscription
    - invoice.payment_failed: Handle failed payment
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Invalid webhook payload")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid webhook signature")
        return HttpResponse(status=400)
    
    # Handle the event
    event_type = event['type']
    
    if event_type == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_session_completed(session)
        
    elif event_type == 'customer.subscription.updated':
        subscription = event['data']['object']
        handle_subscription_updated(subscription)
        
    elif event_type == 'customer.subscription.deleted':
        subscription = event['data']['object']
        handle_subscription_deleted(subscription)
        
    elif event_type == 'invoice.payment_failed':
        invoice = event['data']['object']
        handle_payment_failed(invoice)
    
    return HttpResponse(status=200)


def handle_checkout_session_completed(session):
    """Handle successful checkout session."""
    try:
        user_id = session['metadata']['user_id']
        plan_tier = session['metadata']['plan_tier']
        customer_id = session['customer']
        subscription_id = session['subscription']
        
        user = User.objects.get(id=user_id)
        plan = SubscriptionPlan.objects.get(tier=plan_tier)
        
        # Update or create user subscription
        subscription, created = UserSubscription.objects.update_or_create(
            user=user,
            defaults={
                'plan': plan,
                'stripe_customer_id': customer_id,
                'stripe_subscription_id': subscription_id,
                'is_active': True,
            }
        )
        
        logger.info(f"Subscription {'created' if created else 'updated'} for user {user.email}")
        
    except Exception as e:
        logger.error(f"Error handling checkout session: {str(e)}")


def handle_subscription_updated(stripe_subscription):
    """Handle subscription update (e.g., plan change)."""
    try:
        subscription_id = stripe_subscription['id']
        status = stripe_subscription['status']
        
        user_subscription = UserSubscription.objects.get(stripe_subscription_id=subscription_id)
        
        # Update status
        user_subscription.is_active = (status == 'active')
        user_subscription.save(update_fields=['is_active'])
        
        logger.info(f"Subscription {subscription_id} updated to status: {status}")
        
    except UserSubscription.DoesNotExist:
        logger.warning(f"Subscription {subscription_id} not found in database")
    except Exception as e:
        logger.error(f"Error handling subscription update: {str(e)}")


def handle_subscription_deleted(stripe_subscription):
    """Handle subscription cancellation."""
    try:
        subscription_id = stripe_subscription['id']
        
        user_subscription = UserSubscription.objects.get(stripe_subscription_id=subscription_id)
        
        # Downgrade to Free plan
        free_plan = SubscriptionPlan.objects.get(tier='free')
        user_subscription.plan = free_plan
        user_subscription.is_active = False
        user_subscription.stripe_subscription_id = ''
        user_subscription.save()
        
        logger.info(f"Subscription {subscription_id} cancelled, user downgraded to Free")
        
    except UserSubscription.DoesNotExist:
        logger.warning(f"Subscription {subscription_id} not found in database")
    except Exception as e:
        logger.error(f"Error handling subscription deletion: {str(e)}")


def handle_payment_failed(invoice):
    """Handle failed payment."""
    try:
        customer_id = invoice['customer']
        subscription_id = invoice['subscription']
        
        user_subscription = UserSubscription.objects.get(stripe_subscription_id=subscription_id)
        
        # TODO: Send email notification to user
        # TODO: Implement grace period logic
        
        logger.warning(f"Payment failed for subscription {subscription_id}")
        
    except UserSubscription.DoesNotExist:
        logger.warning(f"Subscription {subscription_id} not found in database")
    except Exception as e:
        logger.error(f"Error handling payment failure: {str(e)}")


@login_required
def payment_success(request):
    """Display success page after successful payment."""
    session_id = request.GET.get('session_id')
    
    context = {
        'session_id': session_id,
        'title': '¡Pago Exitoso!',
        'message': 'Tu suscripción ha sido activada correctamente.',
    }
    
    return render(request, 'payments/success.html', context)


@login_required
def payment_cancel(request):
    """Display cancel page when user cancels payment."""
    context = {
        'title': 'Pago Cancelado',
        'message': 'El proceso de pago fue cancelado. Puedes intentarlo nuevamente cuando desees.',
    }
    
    return render(request, 'payments/cancel.html', context)
