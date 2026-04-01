"""Utilities for error message handling and sanitization."""

import re
from typing import Any


def sanitize_error_message(error: Any, max_length: int = 255) -> str:
    """
    Sanitize an error message by removing ANSI codes and truncating.
    
    Args:
        error: The error object or message to sanitize
        max_length: Maximum length of the sanitized message (default 255 to fit in DB VARCHAR)
        
    Returns:
        Sanitized error message string
    """
    error_str = str(error)
    
    # Remove ANSI color codes (regex pattern for ANSI escape sequences)
    # Pattern: \x1b[...m or \033[...m
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m|\033\[[0-9;]*m')
    sanitized = ansi_escape.sub('', error_str)
    
    # Replace newlines and tabs with spaces for cleaner storage
    sanitized = sanitized.replace('\n', ' | ').replace('\t', ' ')
    
    # Remove multiple consecutive spaces
    sanitized = re.sub(r' +', ' ', sanitized).strip()
    
    # Truncate to max_length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length - 3] + '...'
    
    return sanitized
