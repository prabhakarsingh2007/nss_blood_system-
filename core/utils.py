import time
from django.core.cache import cache
from django.utils.crypto import get_random_string

def generate_secure_otp(length=6) -> str:
    """
    Generates a cryptographically secure numeric OTP using Django's get_random_string.
    """
    return get_random_string(length, allowed_chars="0123456789")

def get_client_ip(request) -> str:
    """
    Retrieves the client's IP address from headers.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'unknown')
    return ip

def check_otp_rate_limit(ip_address, action_key, limit=5, lock_duration_sec=300):
    """
    Checks if a specific IP + action_key combination is currently rate-limited.
    Returns (is_allowed, remaining_attempts_or_lock_seconds).
    If is_allowed is False, the second value is the number of lock seconds remaining.
    """
    cache_key_attempts = f"otp_attempts_{ip_address}_{action_key}"
    cache_key_lock = f"otp_lock_{ip_address}_{action_key}"
    
    # Check if a lock exists
    lock_until = cache.get(cache_key_lock)
    if lock_until:
        remaining = int(lock_until - time.time())
        if remaining > 0:
            return False, remaining
        else:
            cache.delete(cache_key_lock)

    attempts = cache.get(cache_key_attempts, 0)
    if attempts >= limit:
        # Enforce lock
        lock_until = time.time() + lock_duration_sec
        cache.set(cache_key_lock, lock_until, lock_duration_sec)
        cache.delete(cache_key_attempts)
        return False, lock_duration_sec

    return True, limit - attempts

def increment_otp_attempts(ip_address, action_key, duration_sec=300):
    """
    Increments the failed attempt count.
    """
    cache_key_attempts = f"otp_attempts_{ip_address}_{action_key}"
    attempts = cache.get(cache_key_attempts, 0)
    cache.set(cache_key_attempts, attempts + 1, duration_sec)

def clear_otp_attempts(ip_address, action_key):
    """
    Clears attempts and lock status upon successful verification.
    """
    cache_key_attempts = f"otp_attempts_{ip_address}_{action_key}"
    cache_key_lock = f"otp_lock_{ip_address}_{action_key}"
    cache.delete(cache_key_attempts)
    cache.delete(cache_key_lock)

def check_request_rate_limit(ip_address, action_key, limit=30, period_sec=60) -> bool:
    """
    Checks if the IP + action_key has exceeded the limit of requests in the given period.
    Returns True if allowed, False if rate-limited.
    """
    cache_key = f"rate_limit_{ip_address}_{action_key}"
    requests_count = cache.get(cache_key)
    
    if requests_count is None:
        cache.set(cache_key, 1, period_sec)
        return True
        
    if requests_count >= limit:
        return False
        
    try:
        cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, period_sec)
        
    return True
