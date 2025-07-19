"""
Test suite for Exception Handling
"""
import pytest
from project_x_py.exceptions import (
    ProjectXError,
    ProjectXAuthenticationError,
    ProjectXConnectionError,
    ProjectXOrderError,
    ProjectXInstrumentError,
    ProjectXDataError,
    ProjectXRiskError,
    ProjectXConfigError,
    ProjectXRateLimitError,
    ProjectXValidationError
)


class TestExceptionHierarchy:
    """Test cases for exception class hierarchy"""
    
    def test_base_exception(self):
        """Test base ProjectXError"""
        # Act & Assert
        with pytest.raises(ProjectXError) as exc_info:
            raise ProjectXError("Base error message")
        
        assert str(exc_info.value) == "Base error message"
        assert isinstance(exc_info.value, Exception)
    
    def test_authentication_error(self):
        """Test authentication error inheritance and behavior"""
        # Act & Assert
        with pytest.raises(ProjectXAuthenticationError) as exc_info:
            raise ProjectXAuthenticationError("Invalid credentials")
        
        assert str(exc_info.value) == "Invalid credentials"
        assert isinstance(exc_info.value, ProjectXError)
        
        # Can also catch as base error
        with pytest.raises(ProjectXError):
            raise ProjectXAuthenticationError("Auth failed")
    
    def test_connection_error(self):
        """Test connection error with details"""
        # Arrange
        error_details = {
            "url": "https://api.topstepx.com",
            "status_code": 503,
            "retry_count": 3
        }
        
        # Act & Assert
        with pytest.raises(ProjectXConnectionError) as exc_info:
            error = ProjectXConnectionError("Connection failed", details=error_details)
            raise error
        
        assert "Connection failed" in str(exc_info.value)
        assert exc_info.value.details == error_details
        assert exc_info.value.details["status_code"] == 503
    
    def test_order_error_with_order_id(self):
        """Test order error with specific order information"""
        # Act & Assert
        with pytest.raises(ProjectXOrderError) as exc_info:
            error = ProjectXOrderError(
                "Order rejected: Insufficient margin",
                order_id="12345",
                instrument="MGC"
            )
            raise error
        
        assert "Insufficient margin" in str(exc_info.value)
        assert exc_info.value.order_id == "12345"
        assert exc_info.value.instrument == "MGC"
    
    def test_instrument_error(self):
        """Test instrument error"""
        # Act & Assert
        with pytest.raises(ProjectXInstrumentError) as exc_info:
            raise ProjectXInstrumentError("Invalid instrument: XYZ")
        
        assert "Invalid instrument: XYZ" in str(exc_info.value)
    
    def test_data_error_with_context(self):
        """Test data error with context information"""
        # Act & Assert
        with pytest.raises(ProjectXDataError) as exc_info:
            error = ProjectXDataError(
                "Data validation failed",
                field="timestamp",
                value="invalid_date",
                expected_type="datetime"
            )
            raise error
        
        assert "Data validation failed" in str(exc_info.value)
        assert exc_info.value.field == "timestamp"
        assert exc_info.value.value == "invalid_date"
    
    def test_risk_error(self):
        """Test risk management error"""
        # Act & Assert
        with pytest.raises(ProjectXRiskError) as exc_info:
            error = ProjectXRiskError(
                "Position size exceeds limit",
                current_size=50,
                max_size=40,
                instrument="MGC"
            )
            raise error
        
        assert "Position size exceeds limit" in str(exc_info.value)
        assert exc_info.value.current_size == 50
        assert exc_info.value.max_size == 40
    
    def test_config_error(self):
        """Test configuration error"""
        # Act & Assert
        with pytest.raises(ProjectXConfigError) as exc_info:
            raise ProjectXConfigError("Invalid configuration: timeout must be positive")
        
        assert "timeout must be positive" in str(exc_info.value)
    
    def test_rate_limit_error(self):
        """Test rate limit error with retry information"""
        # Act & Assert
        with pytest.raises(ProjectXRateLimitError) as exc_info:
            error = ProjectXRateLimitError(
                "Rate limit exceeded",
                retry_after=60,
                limit=100,
                window="1 minute"
            )
            raise error
        
        assert "Rate limit exceeded" in str(exc_info.value)
        assert exc_info.value.retry_after == 60
        assert exc_info.value.limit == 100
    
    def test_validation_error(self):
        """Test validation error with multiple fields"""
        # Arrange
        validation_errors = {
            "price": "Price must be positive",
            "size": "Size must be an integer",
            "side": "Side must be 0 or 1"
        }
        
        # Act & Assert
        with pytest.raises(ProjectXValidationError) as exc_info:
            error = ProjectXValidationError(
                "Order validation failed",
                errors=validation_errors
            )
            raise error
        
        assert "Order validation failed" in str(exc_info.value)
        assert exc_info.value.errors == validation_errors
        assert len(exc_info.value.errors) == 3


class TestExceptionChaining:
    """Test exception chaining and context preservation"""
    
    def test_exception_chaining(self):
        """Test that exceptions can be chained properly"""
        # Act & Assert
        with pytest.raises(ProjectXOrderError) as exc_info:
            try:
                # Simulate lower-level error
                raise ProjectXConnectionError("Network timeout")
            except ProjectXConnectionError as e:
                # Re-raise as order error
                raise ProjectXOrderError("Order submission failed") from e
        
        assert "Order submission failed" in str(exc_info.value)
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, ProjectXConnectionError)
    
    def test_exception_context_preservation(self):
        """Test that exception context is preserved"""
        # Arrange
        original_error = None
        
        # Act
        try:
            raise ProjectXDataError("Invalid data", field="price", value=-100)
        except ProjectXDataError as e:
            original_error = e
        
        # Assert
        assert original_error is not None
        assert original_error.field == "price"
        assert original_error.value == -100


class TestExceptionHandlingPatterns:
    """Test common exception handling patterns"""
    
    def test_catch_all_project_x_errors(self):
        """Test catching all ProjectX errors with base class"""
        # Arrange
        errors = [
            ProjectXAuthenticationError("Auth failed"),
            ProjectXConnectionError("Connection lost"),
            ProjectXOrderError("Order rejected"),
            ProjectXDataError("Bad data")
        ]
        
        # Act & Assert
        for error in errors:
            with pytest.raises(ProjectXError):
                raise error
    
    def test_specific_error_handling(self):
        """Test handling specific error types differently"""
        # Arrange
        def process_order():
            # Simulate different error scenarios
            import random
            error_type = random.choice(["auth", "risk", "connection"])
            
            if error_type == "auth":
                raise ProjectXAuthenticationError("Token expired")
            elif error_type == "risk":
                raise ProjectXRiskError("Margin exceeded")
            else:
                raise ProjectXConnectionError("Network error")
        
        # Act & Assert
        # Each error type should be catchable individually
        for error_class in [ProjectXAuthenticationError, ProjectXRiskError, ProjectXConnectionError]:
            caught = False
            try:
                # Force specific error
                if error_class == ProjectXAuthenticationError:
                    raise ProjectXAuthenticationError("Test")
                elif error_class == ProjectXRiskError:
                    raise ProjectXRiskError("Test")
                else:
                    raise ProjectXConnectionError("Test")
            except error_class:
                caught = True
            
            assert caught is True
    
    def test_error_message_formatting(self):
        """Test that error messages are properly formatted"""
        # Arrange
        error = ProjectXOrderError(
            "Order validation failed",
            order_id="12345",
            reason="Price outside valid range",
            details={"submitted_price": 2050.0, "valid_range": [2040.0, 2045.0]}
        )
        
        # Act
        error_str = str(error)
        
        # Assert
        assert "Order validation failed" in error_str
        # Additional attributes should be accessible
        assert error.order_id == "12345"
        assert error.reason == "Price outside valid range"
        assert error.details["submitted_price"] == 2050.0
    
    def test_exception_serialization(self):
        """Test that exceptions can be serialized for logging"""
        # Arrange
        error = ProjectXRiskError(
            "Daily loss limit exceeded",
            current_loss=1500.0,
            limit=1000.0,
            account="Test Account"
        )
        
        # Act
        error_dict = {
            "type": error.__class__.__name__,
            "message": str(error),
            "current_loss": getattr(error, 'current_loss', None),
            "limit": getattr(error, 'limit', None),
            "account": getattr(error, 'account', None)
        }
        
        # Assert
        assert error_dict["type"] == "ProjectXRiskError"
        assert error_dict["current_loss"] == 1500.0
        assert error_dict["limit"] == 1000.0
        assert error_dict["account"] == "Test Account"