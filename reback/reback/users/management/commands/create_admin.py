"""
Management command to create admin superuser for Railway deployment.
"""
import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Create admin superuser if it doesn't exist"

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Admin email address',
            default=os.environ.get('DJANGO_ADMIN_EMAIL', 'admin@icfes.com')
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Admin password',
            default=os.environ.get('DJANGO_ADMIN_PASSWORD', 'admin123')
        )

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']

        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.WARNING(f'User with email {email} already exists')
            )
            return

        user = User.objects.create_superuser(
            email=email,
            password=password
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created superuser: {email}')
        )
        self.stdout.write(
            self.style.WARNING('IMPORTANT: Change the password after first login!')
        )
