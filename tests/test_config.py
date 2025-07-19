"""
Test suite for Configuration Management
"""
import pytest
import os
import json
import tempfile
from pathlib import Path
from project_x_py.config import ConfigManager, ProjectXConfig
from project_x_py.exceptions import ProjectXConfigError


class TestConfigManagement:
    """Test cases for configuration management functionality"""
    
    def test_default_configuration(self):
        """Test loading default configuration"""
        # Arrange
        config_manager = ConfigManager()
        
        # Act
        config = config_manager.load_config()
        
        # Assert
        assert isinstance(config, ProjectXConfig)
        assert config.api_url == "https://api.topstepx.com/api"
        assert config.timezone == "America/Chicago"
        assert config.timeout_seconds == 30
        assert config.rate_limit_per_minute == 60
        assert config.max_retries == 3
        assert config.log_level == "INFO"
    
    def test_environment_variable_override(self):
        """Test environment variables override default config"""
        # Arrange
        os.environ["PROJECT_X_API_URL"] = "https://test.api.com"
        os.environ["PROJECT_X_TIMEOUT"] = "60"
        os.environ["PROJECT_X_RATE_LIMIT"] = "120"
        os.environ["PROJECT_X_LOG_LEVEL"] = "DEBUG"
        
        config_manager = ConfigManager()
        
        try:
            # Act
            config = config_manager.load_config()
            
            # Assert
            assert config.api_url == "https://test.api.com"
            assert config.timeout_seconds == 60
            assert config.rate_limit_per_minute == 120
            assert config.log_level == "DEBUG"
        finally:
            # Cleanup
            del os.environ["PROJECT_X_API_URL"]
            del os.environ["PROJECT_X_TIMEOUT"]
            del os.environ["PROJECT_X_RATE_LIMIT"]
            del os.environ["PROJECT_X_LOG_LEVEL"]
    
    def test_configuration_file_loading(self):
        """Test loading configuration from file"""
        # Arrange
        config_data = {
            "api_url": "https://custom.api.com",
            "timeout_seconds": 45,
            "rate_limit_per_minute": 90,
            "timezone": "UTC",
            "log_level": "WARNING"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name
        
        try:
            config_manager = ConfigManager(config_file)
            
            # Act
            config = config_manager.load_config()
            
            # Assert
            assert config.api_url == "https://custom.api.com"
            assert config.timeout_seconds == 45
            assert config.rate_limit_per_minute == 90
            assert config.timezone == "UTC"
            assert config.log_level == "WARNING"
        finally:
            # Cleanup
            os.unlink(config_file)
    
    def test_configuration_file_not_found(self):
        """Test handling of missing configuration file"""
        # Arrange
        config_manager = ConfigManager("non_existent_file.json")
        
        # Act
        config = config_manager.load_config()
        
        # Assert - Should fall back to defaults
        assert config.api_url == "https://api.topstepx.com/api"
        assert config.timeout_seconds == 30
    
    def test_invalid_configuration_file(self):
        """Test handling of invalid configuration file"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content {")
            config_file = f.name
        
        try:
            config_manager = ConfigManager(config_file)
            
            # Act & Assert
            with pytest.raises(ProjectXConfigError):
                config_manager.load_config()
        finally:
            # Cleanup
            os.unlink(config_file)
    
    def test_configuration_precedence(self):
        """Test configuration precedence: env vars > file > defaults"""
        # Arrange
        # Set up file config
        config_data = {
            "api_url": "https://file.api.com",
            "timeout_seconds": 45,
            "rate_limit_per_minute": 90
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name
        
        # Set up env var (should override file)
        os.environ["PROJECT_X_TIMEOUT"] = "120"
        
        try:
            config_manager = ConfigManager(config_file)
            
            # Act
            config = config_manager.load_config()
            
            # Assert
            assert config.api_url == "https://file.api.com"  # From file
            assert config.timeout_seconds == 120  # From env var (overrides file)
            assert config.rate_limit_per_minute == 90  # From file
            assert config.timezone == "America/Chicago"  # Default
        finally:
            # Cleanup
            os.unlink(config_file)
            del os.environ["PROJECT_X_TIMEOUT"]
    
    def test_configuration_validation(self):
        """Test configuration value validation"""
        # Arrange
        config_manager = ConfigManager()
        
        # Test invalid timeout
        os.environ["PROJECT_X_TIMEOUT"] = "-1"
        
        try:
            # Act & Assert
            with pytest.raises(ProjectXConfigError) as exc_info:
                config_manager.load_config()
            
            assert "timeout" in str(exc_info.value).lower()
        finally:
            del os.environ["PROJECT_X_TIMEOUT"]
    
    def test_configuration_save(self):
        """Test saving configuration to file"""
        # Arrange
        config = ProjectXConfig(
            api_url="https://save.api.com",
            timeout_seconds=90,
            rate_limit_per_minute=180
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_file = f.name
        
        try:
            config_manager = ConfigManager(config_file)
            
            # Act
            config_manager.save_config(config)
            
            # Verify by loading
            loaded_config = config_manager.load_config()
            
            # Assert
            assert loaded_config.api_url == "https://save.api.com"
            assert loaded_config.timeout_seconds == 90
            assert loaded_config.rate_limit_per_minute == 180
        finally:
            # Cleanup
            os.unlink(config_file)
    
    def test_configuration_to_dict(self):
        """Test converting configuration to dictionary"""
        # Arrange
        config = ProjectXConfig(
            api_url="https://test.api.com",
            timeout_seconds=60
        )
        
        # Act
        config_dict = config.to_dict()
        
        # Assert
        assert isinstance(config_dict, dict)
        assert config_dict["api_url"] == "https://test.api.com"
        assert config_dict["timeout_seconds"] == 60
        assert "timezone" in config_dict
        assert "rate_limit_per_minute" in config_dict
    
    def test_configuration_from_dict(self):
        """Test creating configuration from dictionary"""
        # Arrange
        config_dict = {
            "api_url": "https://dict.api.com",
            "timeout_seconds": 75,
            "timezone": "Europe/London",
            "log_level": "ERROR"
        }
        
        # Act
        config = ProjectXConfig.from_dict(config_dict)
        
        # Assert
        assert config.api_url == "https://dict.api.com"
        assert config.timeout_seconds == 75
        assert config.timezone == "Europe/London"
        assert config.log_level == "ERROR"
    
    def test_configuration_update(self):
        """Test updating configuration values"""
        # Arrange
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Act
        config.timeout_seconds = 120
        config.rate_limit_per_minute = 240
        
        # Assert
        assert config.timeout_seconds == 120
        assert config.rate_limit_per_minute == 240
    
    def test_websocket_configuration(self):
        """Test WebSocket specific configuration"""
        # Arrange
        config = ProjectXConfig()
        
        # Assert
        assert hasattr(config, 'websocket_url')
        assert hasattr(config, 'websocket_ping_interval')
        assert hasattr(config, 'websocket_reconnect_delay')
        assert config.websocket_ping_interval == 30
        assert config.websocket_reconnect_delay == 5