"""Main test entry point for ProjectX client module tests."""

import pytest

from project_x_py import ProjectX

# This file serves as a main entry point for running client tests.
# It also includes some basic smoke tests for the client initialization.


@pytest.mark.asyncio
async def test_client_import():
    """Test that the client can be imported successfully."""
    assert ProjectX is not None


@pytest.mark.asyncio
async def test_client_instantiation():
    """Test that the client can be instantiated."""
    client = ProjectX(username="test", api_key="test-key")
    assert client is not None
    assert client.username == "test"
    assert client.api_key == "test-key" # pragma: allowlist secret
    assert client.account_name is None


@pytest.mark.asyncio
async def test_client_with_account():
    """Test that the client can be instantiated with an account name."""
    client = ProjectX(username="test", api_key="test-key", account_name="Test Account")
    assert client.account_name == "Test Account"
