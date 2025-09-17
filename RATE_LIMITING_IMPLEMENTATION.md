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
- **LocMemCache** - Local memory cache backend (development)

### 4. Frontend Error Handling

Both chat interfaces (`chat.html` and `demo_chat.html`) include JavaScript error handling that:
- Detects HTTP 429 responses (rate limit exceeded)
- Displays user-friendly error messages
- Prevents additional requests when rate limited

### 5. Configuration Files

#### Settings (`findus/settings.py`)
```python
# Rate limiting cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Database sessions for rate limiting
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = True
```

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

For production deployment, replace the `LocMemCache` with a shared cache backend like Redis or Memcached:

```python
# Production cache configuration (example with Redis)
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

For Heroku deployment with Redis:
1. Add Redis addon: `heroku addons:create heroku-redis:mini`
2. Install django-redis: `uv add django-redis`
3. Update cache configuration to use `REDIS_URL` environment variable

## Benefits

1. **Cost Control** - Prevents excessive Gemini API usage
2. **DoS Protection** - Protects against abuse and excessive requests
3. **User Experience** - Clear error messages when limits are exceeded
4. **Scalability** - Works with both single-instance and multi-instance deployments

## Testing

Due to cache backend limitations in development, comprehensive testing should be done in a production-like environment with Redis or Memcached.

## Files Modified

- `chat/views.py` - Added rate limiting decorators and error handling
- `findus/settings.py` - Added cache and session configuration
- `findus/ratelimit_middleware.py` - Created middleware for exception handling
- `chat/templates/chat/chat.html` - Added frontend error handling
- `chat/templates/chat/demo_chat.html` - Added frontend error handling
