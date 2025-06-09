from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.core.cache import cache
from django.core.exceptions import ValidationError
from unicom.models import Message, Channel
import uuid
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

def validate_tracking_id(tracking_id):
    """Validate the tracking ID format"""
    try:
        return str(uuid.UUID(str(tracking_id)))
    except (ValueError, AttributeError, TypeError):
        return None

def get_rate_limit_key(view_name, tracking_id, client_ip):
    """Generate a rate limit cache key"""
    return f"email_tracking:{view_name}:{tracking_id}:{client_ip}"

def check_rate_limit(key, max_requests=60, window=60):
    """
    Rate limiting function
    max_requests: maximum number of requests allowed in the time window
    window: time window in seconds
    """
    current = cache.get(key, 0)
    if current >= max_requests:
        return False
    
    cache.get_or_set(key, 0, window)
    cache.incr(key)
    return True

@csrf_exempt
@require_GET
def tracking_pixel(request, tracking_id):
    """
    Handle email open tracking via a 1x1 transparent pixel.
    Includes rate limiting and input validation.
    """
    # Validate tracking ID
    valid_id = validate_tracking_id(tracking_id)
    if not valid_id:
        return HttpResponse('Invalid tracking ID', status=400)

    # Rate limiting
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
    rate_key = get_rate_limit_key('pixel', valid_id, client_ip)
    if not check_rate_limit(rate_key):
        return HttpResponse('Too many requests', status=429)

    # Cache the message lookup
    cache_key = f'tracking_message:{valid_id}'
    message = cache.get(cache_key)
    if not message:
        message = get_object_or_404(Message, tracking_id=valid_id)
        cache.set(cache_key, message, timeout=300)  # Cache for 5 minutes

    if not message.opened:
        message.opened = True
        message.time_opened = timezone.now()
        message.save(update_fields=['opened', 'time_opened'])
    
    # Return a 1x1 transparent GIF
    transparent_pixel = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
    return HttpResponse(transparent_pixel, content_type='image/gif')

@csrf_exempt
@require_GET
def link_click(request, tracking_id, link_index):
    """
    Handle email link click tracking and redirect to the original URL.
    Includes rate limiting, input validation, and efficient lookups.
    """
    # Validate tracking ID
    valid_id = validate_tracking_id(tracking_id)
    if not valid_id:
        return HttpResponse('Invalid tracking ID', status=400)

    # Validate link index
    try:
        link_index = int(link_index)
        if link_index < 0:
            raise ValueError
    except (ValueError, TypeError):
        return HttpResponse('Invalid link index', status=400)

    # Rate limiting
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
    rate_key = get_rate_limit_key('link', valid_id, client_ip)
    if not check_rate_limit(rate_key):
        return HttpResponse('Too many requests', status=429)

    # Cache the message lookup
    cache_key = f'tracking_message:{valid_id}'
    message = cache.get(cache_key)
    if not message:
        message = get_object_or_404(Message, tracking_id=valid_id)
        cache.set(cache_key, message, timeout=300)  # Cache for 5 minutes

    try:
        original_url = message.raw.get('original_urls', [])[link_index]
        if not original_url:
            raise IndexError
    except (IndexError, KeyError):
        return HttpResponse('Invalid link', status=400)
    
    # Update link click tracking
    now = timezone.now()
    if not message.link_clicked:
        message.link_clicked = True
        message.time_link_clicked = now
    
    if original_url not in message.clicked_links:
        message.clicked_links.append(original_url)
    
    message.save(update_fields=['link_clicked', 'time_link_clicked', 'clicked_links'])
    
    # Redirect to the original URL with tracking id as a parameter if configured
    tracking_param = message.channel.config.get('TRACKING_PARAMETER_ID')
    if tracking_param:
        parsed = urlparse(original_url)
        query = parse_qs(parsed.query)
        query[tracking_param] = [str(tracking_id)]
        new_query = urlencode(query, doseq=True)
        new_url = urlunparse(parsed._replace(query=new_query))
        return HttpResponseRedirect(new_url)
    else:
        return HttpResponseRedirect(original_url) 