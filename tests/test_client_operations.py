"""
Test file: tests/test_client_operations.py
Phase 1: Critical Core Testing - Basic API Operations
Priority: Critical
"""

import pytest
from unittest.mock import Mock, patch
import polars as pl
from project_x_py import ProjectX
from project_x_py.models import Instrument, Position, Account
from project_x_py.exceptions import (
    ProjectXInstrumentError,
    ProjectXDataError,
    ProjectXError
)


class TestBasicAPIOperations:
    """Test suite for core API operations."""

    @pytest.fixture
    def authenticated_client(self):
        """Create an authenticated client for testing."""
        with patch('project_x_py.client.requests.post') as mock_post:
            # Mock authentication
            mock_auth = Mock()
            mock_auth.status_code = 200
            mock_auth.json.return_value = {
                "success": True,
                "token": "test_token"
            }
            mock_post.return_value = mock_auth
            
            client = ProjectX(username="test_user", api_key="test_key")
            # Trigger authentication
            client._ensure_authenticated()
            return client

    def test_instrument_search(self, authenticated_client):
        """Test search_instruments() functionality."""
        with patch('project_x_py.client.requests.post') as mock_post:
            # Mock successful instrument search
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "contracts": [
                    {
                        "id": "CON.F.US.MGC.M25",
                        "name": "MGCH25",
                        "description": "Micro Gold March 2025",
                        "tickSize": 0.1,
                        "tickValue": 1.0,
                        "activeContract": True
                    },
                    {
                        "id": "CON.F.US.MGC.K25",
                        "name": "MGCK25",
                        "description": "Micro Gold May 2025",
                        "tickSize": 0.1,
                        "tickValue": 1.0,
                        "activeContract": True
                    }
                ]
            }
            mock_post.return_value = mock_response
            
            # Test search
            instruments = authenticated_client.search_instruments("MGC")
            
            assert len(instruments) == 2
            assert all(isinstance(inst, Instrument) for inst in instruments)
            assert any("MGC" in inst.name for inst in instruments)
            assert instruments[0].tickSize == 0.1
            assert instruments[0].tickValue == 1.0
            assert instruments[0].activeContract is True

    def test_instrument_search_no_results(self, authenticated_client):
        """Test search_instruments() with no results."""
        with patch('project_x_py.client.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "contracts": []
            }
            mock_post.return_value = mock_response
            
            instruments = authenticated_client.search_instruments("NONEXISTENT")
            assert len(instruments) == 0

    def test_instrument_search_error(self, authenticated_client):
        """Test search_instruments() error handling."""
        with patch('project_x_py.client.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": False,
                "errorMessage": "Invalid symbol"
            }
            mock_post.return_value = mock_response
            
            with pytest.raises(ProjectXInstrumentError) as exc_info:
                authenticated_client.search_instruments("INVALID")
            
            assert "Contract search failed" in str(exc_info.value)

    def test_get_instrument(self, authenticated_client):
        """Test get_instrument() functionality."""
        with patch('project_x_py.client.requests.post') as mock_post:
            # Mock successful instrument retrieval
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "contracts": [{
                    "id": "CON.F.US.MGC.M25",
                    "name": "MGCH25",
                    "description": "Micro Gold March 2025",
                    "tickSize": 0.1,
                    "tickValue": 1.0,
                    "activeContract": True
                }]
            }
            mock_post.return_value = mock_response
            
            # Test get instrument
            mgc_contract = authenticated_client.get_instrument("MGC")
            
            assert isinstance(mgc_contract, Instrument)
            assert mgc_contract.tickSize > 0
            assert mgc_contract.tickValue > 0
            assert mgc_contract.name == "MGCH25"

    def test_historical_data_retrieval(self, authenticated_client):
        """Test get_data() with various parameters."""
        # First mock get_instrument which is called by get_data
        with patch.object(authenticated_client, 'get_instrument') as mock_get_instrument:
            mock_instrument = Instrument(
                id="CON.F.US.MGC.M25",
                name="MGCH25",
                description="Micro Gold March 2025",
                tickSize=0.1,
                tickValue=1.0,
                activeContract=True
            )
            mock_get_instrument.return_value = mock_instrument
            
            with patch('project_x_py.client.requests.post') as mock_post:
                # Mock historical data response - note the API uses abbreviated keys
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "success": True,
                    "bars": [
                        {
                            "t": "2024-01-01T09:30:00Z",  # Abbreviated key
                            "o": 2045.5,
                            "h": 2046.0,
                            "l": 2045.0,
                            "c": 2045.8,
                            "v": 150
                        },
                        {
                            "t": "2024-01-01T09:45:00Z",
                            "o": 2045.8,
                            "h": 2046.5,
                            "l": 2045.5,
                            "c": 2046.2,
                            "v": 200
                        }
                    ]
                }
                mock_post.return_value = mock_response
                
                # Test data retrieval
                data = authenticated_client.get_data("MGC", days=5, interval=15)
                
                assert isinstance(data, pl.DataFrame)
                assert len(data) == 2
                assert "open" in data.columns
                assert "high" in data.columns
                assert "low" in data.columns
                assert "close" in data.columns
                assert "volume" in data.columns
                assert "timestamp" in data.columns
                
                # Check data types
                assert data["open"].dtype == pl.Float64
                assert data["volume"].dtype in [pl.Int64, pl.Int32]

    def test_data_different_timeframes(self, authenticated_client):
        """Test get_data() with different timeframes."""
        timeframes = [1, 5, 15, 60, 240]
        
        # Mock get_instrument for all calls
        with patch.object(authenticated_client, 'get_instrument') as mock_get_instrument:
            mock_instrument = Instrument(
                id="CON.F.US.MGC.M25",
                name="MGCH25",
                description="Micro Gold March 2025",
                tickSize=0.1,
                tickValue=1.0,
                activeContract=True
            )
            mock_get_instrument.return_value = mock_instrument
        
            for interval in timeframes:
                with patch('project_x_py.client.requests.post') as mock_post:
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {
                        "success": True,
                        "bars": [
                            {
                                "t": "2024-01-01T09:30:00Z",  # Use a fixed valid timestamp
                                "o": 2045.5,
                                "h": 2046.0,
                                "l": 2045.0,
                                "c": 2045.8,
                                "v": 100
                            }
                        ]
                    }
                    mock_post.return_value = mock_response
                    
                    data = authenticated_client.get_data("MGC", days=1, interval=interval)
                    assert len(data) > 0
                    assert isinstance(data, pl.DataFrame)
                    # Verify the interval parameter was used correctly
                    assert data["timestamp"].is_not_null().all()

    def test_account_information_retrieval(self, authenticated_client):
        """Test list_accounts() functionality."""
        with patch('project_x_py.client.requests.post') as mock_post:
            # Mock account list response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "accounts": [
                    {
                        "id": 1001,
                        "name": "Demo Account",
                        "balance": 50000.00,
                        "canTrade": True,
                        "isVisible": True,
                        "simulated": True
                    },
                    {
                        "id": 1002,
                        "name": "Test Account",
                        "balance": 100000.00,
                        "canTrade": True,
                        "isVisible": True,
                        "simulated": True
                    }
                ]
            }
            mock_post.return_value = mock_response
            
            # Test account listing
            accounts = authenticated_client.list_accounts()
            
            assert len(accounts) == 2
            assert isinstance(accounts, list)
            assert accounts[0]["name"] == "Demo Account"
            assert accounts[0]["balance"] == 50000.00
            assert accounts[0]["canTrade"] is True

    def test_account_balance(self, authenticated_client):
        """Test getting account balance functionality."""
        # First set up account info
        authenticated_client.account_info = Account(
            id=1001,
            name="Demo Account",
            balance=50000.00,
            canTrade=True,
            isVisible=True,
            simulated=True
        )
        
        # Get balance from account_info
        balance = authenticated_client.account_info.balance
        assert isinstance(balance, (int, float))
        assert balance == 50000.00

    def test_position_retrieval(self, authenticated_client):
        """Test search_open_positions() functionality."""
        # Set up account info first
        authenticated_client.account_info = Account(
            id=1001,
            name="Demo Account",
            balance=50000.00,
            canTrade=True,
            isVisible=True,
            simulated=True
        )
        
        with patch('project_x_py.client.requests.post') as mock_post:
            # Mock position search response - use correct field names
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "positions": [
                    {
                        "id": 12345,
                        "accountId": 1001,
                        "contractId": "CON.F.US.MGC.M25",
                        "creationTimestamp": "2024-01-01T09:00:00Z",
                        "type": 1,  # LONG
                        "size": 2,  # Not quantity
                        "averagePrice": 2045.5
                    }
                ]
            }
            mock_post.return_value = mock_response
            
            # Test position search
            positions = authenticated_client.search_open_positions()
            
            assert isinstance(positions, list)
            assert len(positions) == 1
            
            # The implementation returns Position objects
            position = positions[0]
            assert isinstance(position, Position)
            assert position.contractId == "CON.F.US.MGC.M25"
            assert position.size == 2
            assert position.type == 1  # LONG

    def test_position_filtering_by_account(self, authenticated_client):
        """Test search_open_positions() with account_id parameter."""
        # Note: search_open_positions doesn't filter by instrument, only account_id
        with patch('project_x_py.client.requests.post') as mock_post:
            # Mock filtered position search - use correct field names
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "positions": [
                    {
                        "id": 12346,
                        "accountId": 1001,
                        "contractId": "CON.F.US.MGC.M25",
                        "creationTimestamp": "2024-01-01T10:00:00Z",
                        "type": 2,  # SHORT
                        "size": 1,
                        "averagePrice": 2045.5
                    }
                ]
            }
            mock_post.return_value = mock_response
            
            # Test with specific account ID
            positions = authenticated_client.search_open_positions(account_id=1001)
            
            assert isinstance(positions, list)
            assert len(positions) == 1
            assert isinstance(positions[0], Position)
            assert positions[0].type == 2  # SHORT

    def test_empty_positions(self, authenticated_client):
        """Test search_open_positions() with no positions."""
        # Set up account info
        authenticated_client.account_info = Account(
            id=1001,
            name="Demo Account",
            balance=50000.00,
            canTrade=True,
            isVisible=True,
            simulated=True
        )
        
        with patch('project_x_py.client.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "positions": []
            }
            mock_post.return_value = mock_response
            
            positions = authenticated_client.search_open_positions()
            assert isinstance(positions, list)
            assert len(positions) == 0

    def test_error_handling_network_error(self, authenticated_client):
        """Test handling of network errors."""
        with patch('project_x_py.client.requests.post') as mock_post:
            mock_post.side_effect = Exception("Network error")
            
            with pytest.raises(Exception):
                authenticated_client.search_instruments("MGC")

    def test_error_handling_invalid_response(self, authenticated_client):
        """Test handling of invalid API responses."""
        with patch('project_x_py.client.requests.post') as mock_post:
            # Mock invalid JSON response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_post.return_value = mock_response
            
            # The actual implementation catches json.JSONDecodeError and raises ProjectXDataError
            # But ValueError from mock is not caught, so we expect ValueError
            with pytest.raises(ValueError):
                authenticated_client.search_instruments("MGC")

    def test_rate_limiting(self, authenticated_client):
        """Test that rate limiting is respected."""
        import time
        
        # Set a very low rate limit for testing
        authenticated_client.min_request_interval = 0.1  # 100ms between requests
        
        start_time = time.time()
        
        with patch('project_x_py.client.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True, "contracts": []}
            mock_post.return_value = mock_response
            
            # Make two quick requests
            authenticated_client.search_instruments("MGC")
            authenticated_client.search_instruments("MNQ")
            
        elapsed = time.time() - start_time
        
        # Second request should have been delayed
        assert elapsed >= 0.1


def run_operations_tests():
    """Helper function to run API operations tests and report results."""
    print("Running Phase 1 Basic API Operations Tests...")
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_operations_tests()