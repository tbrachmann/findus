"""chat.apps module.

Django application configuration for the *chat* app used by the **findus**
project.
"""

from django.apps import AppConfig


class ChatConfig(AppConfig):
    """Django ``AppConfig`` for the **chat** application."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chat'
