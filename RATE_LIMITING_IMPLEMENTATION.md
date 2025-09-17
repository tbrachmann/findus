# Rate Limiting Implementation

## Overview

This document describes the rate limiting implementation added to the findus chat application to control API usage and save costs with the Gemini API.

## Implementation Details

### 1. Rate Limiting Rules

The following rate limits have been implemented:

- **IP-based limits:**
  - 10 requests per hour per IP address
  - 100 requests per day per IP address

- **Session-based limits:**
  - 5 requests per hour per session

### 2. Applied to Views

Rate limiting is applied to these endpoints:
- `/send/` - authenticated user message sending
- `/demo/send/` - demo mode message sending

### 3. Technology Stack

- **django-ratelimit** - Rate limiting library
- **Database sessions** - Session storage for rate limiting keys
- **Custom database cache** - Database-backed cache with atomic increment support

### 4. Frontend Error Handling

Both chat interfaces (`chat.html` and `demo_chat.html`) include JavaScript error handling that:
- Detects HTTP 429 responses (rate limit exceeded)
- Displays user-friendly error messages
- Prevents additional requests when rate limited

### 5. Configuration Files

#### Settings (`findus/settings.py`)
```python
# Rate limiting cache configuration - custom database cache with atomic increment
CACHES = {
    'default': {
        'BACKEND': 'findus.cache_backends.RateLimitDatabaseCache',
        'LOCATION': 'rate_limit_cache_table',
    }
}

# Database sessions for rate limiting
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = True
```

#### Custom Cache Backend (`findus/cache_backends.py`)
Custom database cache backend that provides atomic increment operations required by django-ratelimit.

#### Middleware (`findus/ratelimit_middleware.py`)
Custom middleware to catch `Ratelimited` exceptions and return proper JSON responses.

### 6. View Decorators

```python
@ratelimit(key='ip', rate='10/h', method='POST')  # 10 requests per hour per IP
@ratelimit(key='ip', rate='100/d', method='POST')  # 100 requests per day per IP
@ratelimit(key='session', rate='5/h', method='POST')  # 5 requests per hour per session
```

### 7. Error Response Format

When rate limited, the API returns:
```json
{
    "error": "Rate limit exceeded. Please wait before sending another message."
}
```
With HTTP status code 429.

## Production Deployment Notes

### Cache Backend

The current implementation uses a custom database cache backend that works without Redis. For high-traffic production deployments, you can optionally upgrade to Redis for better performance:

```python
# Optional: High-performance Redis configuration for heavy load
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

### Heroku Deployment

The current implementation works on Heroku out-of-the-box using the database cache. For optional Redis optimization:
1. Add Redis addon: `heroku addons:create heroku-redis:mini`
2. Install django-redis: `uv add django-redis`
3. Update cache configuration to use `REDIS_URL` environment variable

**Setup Commands:**
```bash
# Create cache table during deployment
heroku run python manage.py createcachetable rate_limit_cache_table
```

## Benefits

1. **Cost Control** - Prevents excessive Gemini API usage
2. **DoS Protection** - Protects against abuse and excessive requests
3. **User Experience** - Clear error messages when limits are exceeded
4. **Scalability** - Works with both single-instance and multi-instance deployments

## Testing

Rate limiting is now fully functional in development using the custom database cache backend. Test by making multiple rapid requests to `/send/` or `/demo/send/` endpoints.

## Files Modified

- `chat/views.py` - Added rate limiting decorators and error handling
- `findus/settings.py` - Added cache and session configuration
- `findus/cache_backends.py` - Custom database cache with atomic increment support
- `findus/ratelimit_middleware.py` - Created middleware for exception handling
- `chat/templates/chat/chat.html` - Added frontend error handling
- `chat/templates/chat/demo_chat.html` - Added frontend error handling
