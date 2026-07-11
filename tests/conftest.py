"""
Pytest configuration and shared fixtures.

This file is automatically loaded by pytest.
"""

import pytest
import os

# =============================================================================
# ENVIRONMENT SETUP
# =============================================================================

@pytest.fixture(autouse=True)
def set_test_env():
    """
    Set testing environment variables.
    """
    os.environ["TESTING"] = "true"
    os.environ["DRY_RUN"] = "true"
    yield
    del os.environ["TESTING"]
    del os.environ["DRY_RUN"]


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

def pytest_configure(config):
    """
    Register custom markers.
    """
    config.addinivalue_line("markers", "p0: P0 critical vuln tests")
    config.addinivalue_line("markers", "high: High concern tests")
    config.addinivalue_line("markers", "edge: Edge case tests")
    config.addinivalue_line("markers", "integration: Full integration tests")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def pytest_collection_modifyitems(config, items):
    """
    Organize tests by marker for easier filtering.
    """
    pass  # Default behavior is fine
