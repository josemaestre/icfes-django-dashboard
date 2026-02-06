"""
Celery tasks for Wompi recurring payments.
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from reback.users.subscription_models import UserSubscription, SubscriptionPlan
from reback.users.wompi_client import wompi_client

logger = logging.getLogger(__name__)


@shared_task
def charge_monthly_subscriptions():
    """
    Charge all active subscriptions that are due for renewal.
    Runs daily via Celery Beat.
    """
    logger.info("Starting monthly subscription charges")
    
    # Get all active subscriptions (excluding Free)
    subscriptions = UserSubscription.objects.filter(
        is_active=True,
        plan__tier__in=['basic', 'premium', 'enterprise']
    ).select_related('user', 'plan')
    
    charged_count = 0
    failed_count = 0
    
    for subscription in subscriptions:
        # Check if subscription is due for renewal (30 days since start)
        days_since_start = (timezone.now() - subscription.start_date).days
        
        if days_since_start > 0 and days_since_start % 30 == 0:
            # Time to charge
            success = charge_subscription(subscription)
            if success:
                charged_count += 1
            else:
                failed_count += 1
    
    logger.info(f"Charged {charged_count} subscriptions, {failed_count} failed")
    return {
        'charged': charged_count,
        'failed': failed_count
    }


def charge_subscription(subscription: UserSubscription) -> bool:
    """
    Charge a single subscription using saved payment method.
    
    Returns:
        True if charge was successful
    """
    try:
        # Check if we have a saved payment method
        if not subscription.wompi_payment_method_id:
            logger.warning(f"No payment method for subscription {subscription.id}")
            return False
        
        # Create transaction
        reference = f"recurring-{subscription.plan.tier}-{subscription.user.id}-{timezone.now().timestamp()}"
        amount_in_cents = int(float(subscription.plan.price_monthly) * 100)
        
        result = wompi_client.create_transaction(
            amount_in_cents=amount_in_cents,
            currency="COP",
            customer_email=subscription.user.email,
            reference=reference,
            payment_method_type="CARD",
            payment_source_id=subscription.wompi_payment_method_id
        )
        
        if 'error' in result:
            logger.error(f"Error charging subscription {subscription.id}: {result['error']}")
            return False
        
        # Check transaction status
        transaction = result.get('data', {})
        status = transaction.get('status')
        
        if status == 'APPROVED':
            logger.info(f"Successfully charged subscription {subscription.id}")
            return True
        else:
            logger.warning(f"Transaction not approved for subscription {subscription.id}: {status}")
            
            # If payment failed, deactivate subscription
            if status in ['DECLINED', 'ERROR']:
                subscription.is_active = False
                subscription.save()
                
                # TODO: Send email notification to user
            
            return False
            
    except Exception as e:
        logger.error(f"Exception charging subscription {subscription.id}: {str(e)}")
        return False
