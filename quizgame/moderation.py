import logging
from better_profanity import profanity
from .models import ModerationLog, BlockedIP
from django.http import JsonResponse

logger = logging.getLogger(__name__)

def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def is_ip_blocked(ip_address):
    """Check if an IP address is in the blocklist."""
    return BlockedIP.objects.filter(ip_address=ip_address).exists()

def check_and_flag_content(request, content):
    """Check content for profanity, log the attempt, and return if it's suspicious."""
    if not content or not isinstance(content, str):
        return False, None

    user = request.user if request.user.is_authenticated else None
    ip_address = get_client_ip(request)

    # Check for profanity
    is_suspicious = profanity.contains_profanity(content)

    # Log the attempt
    ModerationLog.objects.create(
        user=user,
        ip_address=ip_address,
        content=content,
        is_suspicious=is_suspicious
    )

    if is_suspicious:
        logger.warning(f"Suspicious content detected from IP: {ip_address}. User: {user}. Content: {content}")
        
        # Prepare a response to set a cookie
        response = JsonResponse({'error': 'Inappropriate content detected.'}, status=403)
        response.set_cookie('flagged_user', 'true', max_age=365 * 24 * 60 * 60) # Cookie for 1 year
        return True, response

    return False, None
