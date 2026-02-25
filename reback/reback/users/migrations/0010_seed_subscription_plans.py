"""
Data migration: seed the 4 default SubscriptionPlans.
Uses get_or_create so it's safe to run multiple times.
"""
from django.db import migrations


PLANS = [
    {
        "tier": "free",
        "name": "Free",
        "description": "Acceso básico gratuito al dashboard nacional.",
        "price_monthly": "0.00",
        "max_queries_per_day": 20,
        "max_export_rows": None,
        "api_access": False,
        "api_rate_limit": None,
        "access_regions": True,
        "access_departments": False,
        "access_municipalities": False,
        "access_schools": False,
        "years_of_data": 3,
        "export_csv": False,
        "export_excel": False,
        "export_pdf": False,
        "is_active": True,
    },
    {
        "tier": "basic",
        "name": "Basic",
        "description": "Acceso a datos departamentales y exportación CSV.",
        "price_monthly": "29.00",
        "max_queries_per_day": 200,
        "max_export_rows": 5000,
        "api_access": False,
        "api_rate_limit": None,
        "access_regions": True,
        "access_departments": True,
        "access_municipalities": False,
        "access_schools": True,
        "years_of_data": 9,
        "export_csv": True,
        "export_excel": False,
        "export_pdf": True,
        "is_active": True,
    },
    {
        "tier": "premium",
        "name": "Premium",
        "description": "Acceso completo a colegios, municipios, exportación Excel y API.",
        "price_monthly": "79.00",
        "max_queries_per_day": 1000,
        "max_export_rows": 50000,
        "api_access": True,
        "api_rate_limit": 500,
        "access_regions": True,
        "access_departments": True,
        "access_municipalities": True,
        "access_schools": True,
        "years_of_data": 9,
        "export_csv": True,
        "export_excel": True,
        "export_pdf": True,
        "is_active": True,
    },
    {
        "tier": "enterprise",
        "name": "Enterprise",
        "description": "Sin límites. API ilimitada. Para entidades gubernamentales e instituciones.",
        "price_monthly": "299.00",
        "max_queries_per_day": 99999,
        "max_export_rows": None,
        "api_access": True,
        "api_rate_limit": None,
        "access_regions": True,
        "access_departments": True,
        "access_municipalities": True,
        "access_schools": True,
        "years_of_data": 9,
        "export_csv": True,
        "export_excel": True,
        "export_pdf": True,
        "is_active": True,
    },
]


def seed_plans(apps, schema_editor):
    SubscriptionPlan = apps.get_model("users", "SubscriptionPlan")
    for plan_data in PLANS:
        SubscriptionPlan.objects.get_or_create(
            tier=plan_data["tier"],
            defaults=plan_data,
        )


def unseed_plans(apps, schema_editor):
    # Reverse: remove only the seeded tiers (don't delete custom plans)
    SubscriptionPlan = apps.get_model("users", "SubscriptionPlan")
    SubscriptionPlan.objects.filter(
        tier__in=[p["tier"] for p in PLANS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0009_invitacionemail"),
    ]

    operations = [
        migrations.RunPython(seed_plans, reverse_code=unseed_plans),
    ]
