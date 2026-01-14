"""
Management command para crear los planes de suscripción iniciales.
"""
from django.core.management.base import BaseCommand
from reback.users.subscription_models import SubscriptionPlan


class Command(BaseCommand):
    help = 'Create initial subscription plans for ICFES Analytics'

    def handle(self, *args, **options):
        plans_data = [
            {
                'tier': 'free',
                'name': 'Free Plan',
                'description': 'Perfect to get started with ICFES Analytics',
                'price_monthly': 0.00,
                'max_queries_per_day': 10,
                'max_export_rows': None,
                'api_access': False,
                'api_rate_limit': None,
                'access_regions': True,
                'access_departments': False,
                'access_municipalities': False,
                'access_schools': False,
                'years_of_data': 3,
                'export_csv': False,
                'export_excel': False,
                'export_pdf': False,
            },
            {
                'tier': 'basic',
                'name': 'Basic Plan',
                'description': 'For educators and researchers',
                'price_monthly': 9.99,
                'max_queries_per_day': 100,
                'max_export_rows': 1000,
                'api_access': False,
                'api_rate_limit': None,
                'access_regions': True,
                'access_departments': True,
                'access_municipalities': True,
                'access_schools': False,
                'years_of_data': 10,
                'export_csv': True,
                'export_excel': False,
                'export_pdf': False,
            },
            {
                'tier': 'premium',
                'name': 'Premium Plan',
                'description': 'For institutions and advanced users',
                'price_monthly': 29.99,
                'max_queries_per_day': 1000,
                'max_export_rows': None,  # Unlimited
                'api_access': True,
                'api_rate_limit': 100,  # 100 requests/hour
                'access_regions': True,
                'access_departments': True,
                'access_municipalities': True,
                'access_schools': True,
                'years_of_data': 29,  # Full historical data (1996-2024)
                'export_csv': True,
                'export_excel': True,
                'export_pdf': True,
            },
            {
                'tier': 'enterprise',
                'name': 'Enterprise Plan',
                'description': 'Custom solutions for large organizations',
                'price_monthly': 99.99,  # Custom pricing
                'max_queries_per_day': 10000,
                'max_export_rows': None,  # Unlimited
                'api_access': True,
                'api_rate_limit': None,  # Unlimited
                'access_regions': True,
                'access_departments': True,
                'access_municipalities': True,
                'access_schools': True,
                'years_of_data': 29,
                'export_csv': True,
                'export_excel': True,
                'export_pdf': True,
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for plan_data in plans_data:
            plan, created = SubscriptionPlan.objects.update_or_create(
                tier=plan_data['tier'],
                defaults=plan_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'[+] Created plan: {plan.name} (${plan.price_monthly}/mo)')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'[*] Updated plan: {plan.name} (${plan.price_monthly}/mo)')
                )
        
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'Completed! Created {created_count} plans, updated {updated_count} plans.'
            )
        )
