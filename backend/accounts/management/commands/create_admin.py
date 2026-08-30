import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Creates a superuser from environment variables if it does not already exist'

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        if not username or not email or not password:
            self.stdout.write(self.style.WARNING(
                'Missing DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, or DJANGO_SUPERUSER_PASSWORD environment variables. '
                'Superuser creation skipped.'
            ))
            return

        # Check if user already exists
        user = User.objects.filter(username=username).first()
        if not user:
            user = User.objects.filter(email=email).first()

        if user:
            self.stdout.write(self.style.SUCCESS(f'User with username "{user.username}" or email "{user.email}" already exists.'))
            
            # Ensure the existing user is a superuser
            if not user.is_superuser or not user.is_staff:
                user.is_superuser = True
                user.is_staff = True
                user.save()
                self.stdout.write(self.style.SUCCESS(f'User "{user.username}" has been promoted to superuser/staff.'))
                
            if os.environ.get('DJANGO_SUPERUSER_OVERWRITE_PASSWORD') == 'True':
                user.set_password(password)
                user.save()
                self.stdout.write(self.style.SUCCESS(f'Password for superuser "{user.username}" has been updated.'))
            else:
                self.stdout.write(self.style.SUCCESS('Password was not updated (set DJANGO_SUPERUSER_OVERWRITE_PASSWORD=True to overwrite).'))
        else:
            user = User(username=username, email=email, is_superuser=True, is_staff=True)
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Superuser "{username}" created successfully.'))
