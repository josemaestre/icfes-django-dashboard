"""
Migration: Add 'pro' and 'institutional' tiers + max_users field.

Changes:
  - SubscriptionPlan.tier choices updated to include 'pro' and 'institutional'
  - SubscriptionPlan.max_users field added (default=1)
  - Seeds new 'pro' and 'institutional' plans using the actual model field names
"""
from django.db import migrations, models


def seed_new_plans(apps, schema_editor):
    """Create Pro and Institutional plans if they don't exist yet."""
    SubscriptionPlan = apps.get_model('users', 'SubscriptionPlan')

    # Pro plan (maps to old 'basic'/'premium')
    SubscriptionPlan.objects.get_or_create(
        tier='pro',
        defaults={
            'name':                 'Plan Pro Estratégico',
            'price_monthly':        82500,
            'max_queries_per_day':  500,
            'access_regions':       True,
            'access_departments':   True,
            'access_municipalities': True,
            'access_schools':       True,
            'export_csv':           True,
            'export_excel':         True,
            'export_pdf':           False,
            'api_access':           False,
            'years_of_data':        28,
            'max_users':            1,
            'is_active':            True,
        }
    )

    # Institutional plan
    SubscriptionPlan.objects.get_or_create(
        tier='institutional',
        defaults={
            'name':                 'Plan Institucional',
            'price_monthly':        0,      # price defined via sales contact
            'max_queries_per_day':  99999,
            'access_regions':       True,
            'access_departments':   True,
            'access_municipalities': True,
            'access_schools':       True,
            'export_csv':           True,
            'export_excel':         True,
            'export_pdf':           True,
            'api_access':           True,
            'years_of_data':        28,
            'max_users':            10,
            'is_active':            True,
        }
    )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0012_subscriptionplan_billing_period'),
    ]

    operations = [
        # Add max_users field
        migrations.AddField(
            model_name='subscriptionplan',
            name='max_users',
            field=models.IntegerField(
                default=1,
                help_text='Número máximo de usuarios por cuenta (1=individual, 10=institucional)'
            ),
        ),

        # Update tier choices to include new canonical tiers
        migrations.AlterField(
            model_name='subscriptionplan',
            name='tier',
            field=models.CharField(
                choices=[
                    ('free',          'Freemium (Gratis)'),
                    ('pro',           'Pro Estratégico'),
                    ('institutional', 'Institucional'),
                    ('basic',         'Basic (legacy → Pro)'),
                    ('premium',       'Premium (legacy → Pro)'),
                    ('enterprise',    'Enterprise (legacy → Institucional)'),
                ],
                default='free',
                max_length=20,
                unique=True,
            ),
        ),

        # Seed the new plans
        migrations.RunPython(seed_new_plans, migrations.RunPython.noop),
    ]
