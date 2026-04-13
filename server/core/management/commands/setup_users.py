from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import UserProfile

User = get_user_model()


class Command(BaseCommand):
    help = 'Create admin and user accounts for Medicare'

    def handle(self, *args, **kwargs):
        # Create admin account
        admin_username = 'admin'
        admin_password = 'admin@123'
        admin_email = 'admin@medicare.com'

        if User.objects.filter(username=admin_username).exists():
            self.stdout.write(
                self.style.WARNING(f'Admin user "{admin_username}" already exists')
            )
        else:
            admin_user = User.objects.create_superuser(
                username=admin_username,
                email=admin_email,
                password=admin_password,
                first_name='Admin',
                last_name='Medicare'
            )
            self.stdout.write(
                self.style.SUCCESS(f'✅ Admin user created successfully!')
            )
            self.stdout.write(f'   Username: {admin_username}')
            self.stdout.write(f'   Password: {admin_password}')
            self.stdout.write(f'   Email: {admin_email}')

        # Create regular user account
        user_username = 'user'
        user_password = 'user@123'
        user_email = 'user@medicare.com'

        if User.objects.filter(username=user_username).exists():
            self.stdout.write(
                self.style.WARNING(f'User "{user_username}" already exists')
            )
        else:
            regular_user = User.objects.create_user(
                username=user_username,
                email=user_email,
                password=user_password,
                first_name='John',
                last_name='Doe'
            )
            
            # Create user profile
            UserProfile.objects.create(
                user=regular_user,
                phone='+1-234-567-8900',
                blood_group='O+',
                gender='Male'
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Regular user created successfully!')
            )
            self.stdout.write(f'   Username: {user_username}')
            self.stdout.write(f'   Password: {user_password}')
            self.stdout.write(f'   Email: {user_email}')

        self.stdout.write(
            self.style.SUCCESS('\n✅ Setup complete! You can now login with these credentials.')
        )
