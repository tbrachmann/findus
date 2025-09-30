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
