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


def classify_error_category(error: Exception | str) -> str:
    """
    Classify an error into a category for user-friendly messaging.
    
    Categories:
    - 'network': DNS resolution, connection failure, network issues
    - 'auth': Invalid credentials, authentication failure
    - 'timeout': Request/operation timeout (not related to network resolution)
    - 'unavailable': Service unavailable (5xx, provider down)
    - 'invalid_input': Invalid parameters or configuration
    - 'unknown': Unrecognized error type
    
    Args:
        error: The error object or message string to classify
        
    Returns:
        Error category string
    """
    error_str = str(error).lower()
    
    # Network/DNS errors - Check FIRST because they may contain "timeout" or "exceeded"
    if any(pattern in error_str for pattern in [
        'nameresolution',
        'getaddrinfo',
        'dns',
        'failed to resolve',
        'connection refused',
        'connection reset',
        'network unreachable',
        'httpconnectionpool',
        'connectionerror',
        'socket error',
        'errno 11001',  # Windows DNS resolution error
        'errno 111',    # Linux connection refused
    ]):
        return 'network'
    
    # Timeout errors
    if any(pattern in error_str for pattern in [
        'read timed out',
        'write timeout',
        'deadline exceeded',
        'operation timed out',
    ]):
        return 'timeout'

    # Authentication/credential errors
    if any(pattern in error_str for pattern in [
        'unauthorized',
        'authentication',
        'invalid credentials',
        'invalid token',
        'permission denied',
        'forbidden',
        '401',
        '403',
    ]):
        return 'auth'
    
    # Service unavailable
    if any(pattern in error_str for pattern in [
        'service unavailable',
        'internal server error',
        '500',
        '502',
        '503',
        '504',
    ]):
        return 'unavailable'
    
    # Invalid input/parameters
    if any(pattern in error_str for pattern in [
        'invalid',
        'bad request',
        'validation',
        '400',
        'malformed',
    ]):
        return 'invalid_input'
    
    return 'unknown'


def get_user_friendly_error_message(error: Exception | str, error_category: str = '') -> str:
    """
    Get a user-friendly error message based on error category.
    
    Hides technical details while providing actionable guidance.
    
    Args:
        error: The error object or message string
        error_category: Pre-classified error category (optional). If empty, will classify.
        
    Returns:
        User-friendly message safe for UI display
    """
    if not error_category:
        error_category = classify_error_category(error)
    
    messages = {
        'network': 'Unable to establish connection. Please check your network and try again.',
        'auth': 'Authentication failed. Please verify your credentials and try again.',
        'timeout': 'Request took too long. Please try again.',
        'unavailable': 'Service is temporarily unavailable. Please try again later.',
        'invalid_input': 'Invalid configuration. Please check your input and try again.',
        'unknown': 'An unexpected error occurred. Please try again.',
    }
    
    return messages.get(error_category, messages['unknown'])
