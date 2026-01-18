"""
Auto-initialize admin user on first request.
This middleware creates the admin user if it doesn't exist.
"""
from django.contrib.auth import get_user_model
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class AutoCreateAdminMiddleware(MiddlewareMixin):
    """Create admin user automatically if it doesn't exist."""
    
    _admin_created = False
    
    def process_request(self, request):
        # Only try once per server startup
        if AutoCreateAdminMiddleware._admin_created:
            return None
            
        try:
            # Check if any superuser exists
            if not User.objects.filter(is_superuser=True).exists():
                # Create admin user
                admin_email = 'admin@icfes.com'
                admin_password = 'admin123'
                
                User.objects.create_superuser(
                    email=admin_email,
                    password=admin_password
                )
                
                logger.info(f'✅ Auto-created admin user: {admin_email}')
                logger.warning('⚠️  IMPORTANT: Change password after first login!')
            
            AutoCreateAdminMiddleware._admin_created = True
            
        except Exception as e:
            logger.error(f'❌ Failed to auto-create admin: {e}')
        
        return None
