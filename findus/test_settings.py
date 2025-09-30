"""
Test-specific Django settings that extend the main settings.

This module provides default values for environment variables that are required
in the main settings but may not be available in CI/test environments.
"""

import os

# Set dummy environment variables for testing if not already set
if not os.getenv('GEMINI_API_KEY'):
    os.environ['GEMINI_API_KEY'] = 'test-dummy-key-12345'

if not os.getenv('LOGFIRE_KEY'):
    os.environ['LOGFIRE_KEY'] = 'test-dummy-logfire-key-12345'

if not os.getenv('SECRET_KEY'):
    os.environ['SECRET_KEY'] = 'test-secret-key-django-testing-only'

# Import all settings from the main settings module
from .settings import *  # noqa: F403, F401

# Override database settings for testing to prevent connection issues
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'test_db'),
        'USER': os.getenv('POSTGRES_USER', 'test_user'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'test_password'),
        'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
        'CONN_MAX_AGE': 0,  # No persistent connections
        'OPTIONS': {},
        'TEST': {
            'NAME': None,  # Use default test database name
        },
    }
}
