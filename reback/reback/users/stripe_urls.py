"""
URLs for Wompi payment integration.
"""
from django.urls import path
from reback.users import wompi_views

app_name = "payments"

urlpatterns = [
    # Wompi
    path("wompi/checkout/", wompi_views.wompi_checkout, name="wompi_checkout"),
    path("wompi/webhook/", wompi_views.wompi_webhook, name="wompi_webhook"),
    path("wompi/success/", wompi_views.wompi_success, name="wompi_success"),
    
    # Stripe (legacy, keep for future)
    # path("create-checkout-session/", stripe_views.create_checkout_session, name="create_checkout_session"),
    # path("webhook/", stripe_views.stripe_webhook, name="webhook"),
    # path("success/", stripe_views.payment_success, name="success"),
    path("cancel/", wompi_views.wompi_success, name="cancel"),  # Reuse success template
]
