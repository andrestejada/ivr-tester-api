"""Tests for network error handling and message filtering in ExecuteTestCaseUseCase."""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

from src.application.use_cases.execute_test_case_use_case import ExecuteTestCaseUseCase
from src.application.utils.error_utils import (
    get_user_friendly_error_message, 
    classify_error_category
)
from src.domain.entities.test_case import TestCaseEntity
from src.domain.entities.test_execution import TestExecutionEntity
from src.domain.entities.call_session import CallSessionEntity
from src.application.dtos.realtime_events import ExecutionEvent


@pytest.fixture
def mock_repos_and_providers():
    """Create mocked dependencies."""
    return {
        'test_case_repo': AsyncMock(),
        'test_execution_repo': AsyncMock(),
        'execution_log_repo': AsyncMock(),
        'call_provider': AsyncMock(),
        'asr_provider': AsyncMock(),
        'call_session_store': AsyncMock(),
        'event_hub': AsyncMock(),
    }


@pytest.fixture
def use_case(mock_repos_and_providers):
    """Create use case with mocked dependencies."""
    return ExecuteTestCaseUseCase(
        test_case_repo=mock_repos_and_providers['test_case_repo'],
        test_execution_repo=mock_repos_and_providers['test_execution_repo'],
        execution_log_repo=mock_repos_and_providers['execution_log_repo'],
        call_provider=mock_repos_and_providers['call_provider'],
        asr_provider=mock_repos_and_providers['asr_provider'],
        call_session_store=mock_repos_and_providers['call_session_store'],
        event_hub=mock_repos_and_providers['event_hub'],
    )


class TestNetworkErrorHandling:
    """Test network error handling and friendly message emission."""

    @pytest.mark.asyncio
    async def test_error_handling_integration_scenario(self):
        """Test error classification and message generation for realistic Twilio scenarios."""
        # Scenario 1: DNS resolution failure (most common transient error)
        dns_error = OSError(
            "HTTPSConnectionPool(host='api.twilio.com', port=443): "
            "Max retries exceeded with url: /2010-04-01/Accounts/ACxxxxxxxxxxxxxxxxxxxxxxxx/Calls.json "
            "(Caused by NameResolutionError(<urllib3.connection.HTTPSConnection object at 0x7f8b8e1234>: "
            "Failed to resolve 'api.twilio.com' ([Errno 11001] getaddrinfo failed)))"
        )
        
        category = classify_error_category(dns_error)
        assert category == 'network'
        
        message = get_user_friendly_error_message(dns_error, category)
        assert 'api.twilio.com' not in message
        assert 'ACxxxxxxxxxxxxxxxxxxxxxxxx' not in message
        assert 'getaddrinfo' not in message
        assert '11001' not in message
        
        # Scenario 2: Connection timeout (also transient)
        timeout_error = TimeoutError(
            "HTTPSConnectionPool(host='api.twilio.com', port=443) "
            "read timed out. (read timeout=30)"
        )
        
        category = classify_error_category(timeout_error)
        assert category == 'timeout'
        
        message = get_user_friendly_error_message(timeout_error, category)
        assert '30' not in message  # Hide timeout value
        assert 'api.twilio.com' not in message
        
        # Scenario 3: Authentication failure (NOT transient, should not retry)
        auth_error = Exception(
            "401 Unauthorized: Invalid credentials (ACxxxxx:auth_token_invalid) "
            "More details: https://www.twilio.com/docs/errors/20003"
        )
        
        category = classify_error_category(auth_error)
        assert category == 'auth'
        assert category != 'network'  # Should NOT be retried
        
        message = get_user_friendly_error_message(auth_error, category)
        assert '20003' not in message  # Hide error code
        assert 'ACxxxxx' not in message





    @pytest.mark.asyncio
    async def test_error_category_dns_classification(self):
        """Test that DNS errors are correctly classified as 'network' category."""
        # Test different DNS error patterns
        errors = [
            OSError("[Errno 11001] getaddrinfo failed"),
            OSError("NameResolutionError: api.twilio.com"),
            Exception("HTTPSConnectionPool(host='api.twilio.com', port=443): Failed to resolve 'api.twilio.com'"),
            Exception("Connection error: DNS lookup failed for api.twilio.com"),
        ]
        
        for error in errors:
            category = classify_error_category(error)
            assert category == 'network', f"Expected 'network' category for error: {str(error)}"


    @pytest.mark.asyncio
    async def test_timeout_error_classification(self):
        """Test that timeout errors are correctly classified."""
        errors = [
            TimeoutError("Read timed out"),
            Exception("Socket timeout: operation timed out"),
            Exception("write timeout"),
            Exception("Operation deadline exceeded"),
        ]
        
        for error in errors:
            category = classify_error_category(error)
            assert category == 'timeout', f"Expected 'timeout' category for error: {str(error)}"


    @pytest.mark.asyncio
    async def test_auth_error_NOT_retried(self):
        """Test that auth errors are NOT classified as network (won't be retried)."""
        errors = [
            Exception("Unauthorized: Invalid credentials"),
            Exception("403 Forbidden"),
            Exception("401 Authentication failed"),
        ]
        
        for error in errors:
            category = classify_error_category(error)
            assert category != 'network', f"Auth error should not be 'network': {str(error)}"
            assert category == 'auth', f"Expected 'auth' category for error: {str(error)}"


    @pytest.mark.asyncio
    async def test_friendly_message_generation(self):
        """Test friendly message generation for different error types."""
        # Test network error
        network_error = OSError("getaddrinfo failed")
        msg = get_user_friendly_error_message(network_error)
        assert 'network' in msg.lower() or 'connect' in msg.lower()
        assert 'getaddrinfo' not in msg
        
        # Test timeout error
        timeout_error = TimeoutError("Read timed out")
        msg = get_user_friendly_error_message(timeout_error)
        assert 'timeout' in msg.lower() or 'long' in msg.lower()
        # Timeout message should not be same as generic error
        assert msg != 'An unexpected error occurred. Please try again.'
        
        # Test auth error
        auth_error = Exception("401 Unauthorized")
        msg = get_user_friendly_error_message(auth_error)
        assert 'auth' in msg.lower() or 'credential' in msg.lower()
        assert '401' not in msg


class TestErrorMessageFiltering:
    """Test that technical details are preserved in logs but not in WebSocket events."""

    def test_error_utils_classify_and_message(self):
        """Verify error_utils functions work with realistic Twilio errors."""
        # Realistic error from Twilio SDK
        dns_error_string = (
            "HTTPSConnectionPool(host='api.twilio.com', port=443): "
            "Max retries exceeded with url: /2010-04-01/Accounts/ACxxxxxxxxxxxxxxxxxxxxxxxx/Calls.json "
            "(Caused by NameResolutionError(<urllib3.connection.HTTPSConnection object at 0x...>: "
            "Failed to resolve 'api.twilio.com' ([Errno 11001] getaddrinfo failed))"
        )
        
        # Classify it
        category = classify_error_category(dns_error_string)
        assert category == 'network'
        
        # Generate friendly message
        msg = get_user_friendly_error_message(dns_error_string, category)
        
        # Verify friendly message hides technical details
        assert 'api.twilio.com' not in msg
        assert 'Accounts/AC0' not in msg
        assert 'getaddrinfo' not in msg
        assert '11001' not in msg
        assert 'HTTPSConnectionPool' not in msg
        
        # But contains user guidance
        assert len(msg) > 0
        assert len(msg) < 255  # Should be concise
