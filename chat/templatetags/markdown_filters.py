"""Template filters for Markdown rendering."""

from typing import Any

import markdown  # type: ignore[import-untyped]
from django import template
from django.utils.safestring import SafeString, mark_safe

register = template.Library()


@register.filter  # type: ignore[misc]
def render_markdown(text: Any) -> SafeString:
    """
    Convert Markdown text to HTML.

    This filter processes text through the Python markdown library
    to render Markdown syntax like **bold**, *italic*, etc. as proper HTML.

    Args:
        text: The raw markdown text to be processed

    Returns:
        HTML-safe string with rendered markdown
    """
    if not text:
        return mark_safe("")

    # Configure markdown with extensions for better formatting
    md = markdown.Markdown(
        extensions=[
            'markdown.extensions.fenced_code',  # Support for ```code``` blocks
            'markdown.extensions.codehilite',  # Syntax highlighting
            'markdown.extensions.tables',  # Table support
            'markdown.extensions.nl2br',  # Convert newlines to <br>
        ],
        extension_configs={
            'markdown.extensions.codehilite': {
                'css_class': 'highlight',
                'use_pygments': False,  # Use CSS classes instead of inline styles
            }
        },
    )

    # Convert markdown to HTML
    html = md.convert(str(text))

    # Return as safe HTML (Django won't escape it)
    return mark_safe(html)
