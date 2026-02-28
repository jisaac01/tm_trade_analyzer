"""
Pytest configuration and fixtures for test quality enforcement.

This module provides infrastructure to encourage high-quality testing practices:
- Warns when mocks are used (prefer real data and integration tests)
- Provides utilities for test quality assessment
"""
import pytest
import warnings
import functools
from unittest import mock as original_mock


# Track whether mock warnings are suppressed for a specific test
_suppress_mock_warnings = False


def suppress_mock_warnings(func):
    """
    Decorator to suppress mock usage warnings for a specific test.
    
    Use this ONLY when mocking is genuinely necessary (external APIs, 
    unavoidable I/O, etc.) and document WHY in a comment.
    
    Example:
        @suppress_mock_warnings  # External API call - no test data available
        def test_api_error_handling():
            with patch('requests.get'):
                ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        global _suppress_mock_warnings
        old_value = _suppress_mock_warnings
        _suppress_mock_warnings = True
        try:
            return func(*args, **kwargs)
        finally:
            _suppress_mock_warnings = old_value
    return wrapper


class MockWarningWrapper:
    """Wrapper that warns when mock objects are created."""
    
    def __init__(self, original_class, name):
        self._original_class = original_class
        self._name = name
    
    def __call__(self, *args, **kwargs):
        if not _suppress_mock_warnings:
            warnings.warn(
                f"\n⚠️  MOCKING DETECTED: {self._name} is being used.\n"
                f"   Consider if this test could use real data instead.\n"
                f"   Integration tests with minimal mocking are preferred.\n"
                f"   See tests/test_integration.py for examples.\n"
                f"   If mocking is necessary, add @suppress_mock_warnings decorator\n"
                f"   and a comment explaining why.",
                category=UserWarning,
                stacklevel=2
            )
        return self._original_class(*args, **kwargs)
    
    def __getattr__(self, name):
        # Forward all other attribute access to the original class
        return getattr(self._original_class, name)


def pytest_configure(config):
    """
    Configure pytest to warn on mock usage.
    
    This hook is called during pytest startup. It wraps common mocking
    utilities to emit warnings when they're used, encouraging developers
    to write integration tests with real data instead.
    """
    # Wrap Mock and MagicMock
    original_mock.Mock = MockWarningWrapper(original_mock.Mock, "Mock")
    original_mock.MagicMock = MockWarningWrapper(original_mock.MagicMock, "MagicMock")
    
    # Wrap patch (both as function and decorator)
    _original_patch = original_mock.patch
    
    def warning_patch(*args, **kwargs):
        if not _suppress_mock_warnings:
            target = args[0] if args else kwargs.get('target', 'unknown')
            warnings.warn(
                f"\n⚠️  MOCKING DETECTED: patch('{target}') is being used.\n"
                f"   Consider if this test could use real data instead.\n"
                f"   Integration tests with minimal mocking are preferred.\n"
                f"   See tests/test_integration.py for examples.\n"
                f"   If mocking is necessary, add @suppress_mock_warnings decorator\n"
                f"   and a comment explaining why.",
                category=UserWarning,
                stacklevel=2
            )
        return _original_patch(*args, **kwargs)
    
    # Preserve patch's attributes (object, dict, multiple, etc.)
    for attr in dir(_original_patch):
        if not attr.startswith('_'):
            try:
                setattr(warning_patch, attr, getattr(_original_patch, attr))
            except AttributeError:
                pass
    
    original_mock.patch = warning_patch


# Make suppress decorator available at module level for imports
__all__ = ['suppress_mock_warnings']
