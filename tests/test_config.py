"""
Unit tests for config module
"""
import json
import pytest
import tempfile
import os
from pathlib import Path

from src.config import BackendMCPConfig, ConfigurationManager, ConfigurationError


class TestBackendMCPConfig:
    """Test cases for BackendMCPConfig class"""
    
    def test_initialization_with_separate_command_args(self):
        """Test initialization with separate command and args"""
        config = BackendMCPConfig(
            name="test_backend",
            command="python",
            args=["script.py", "--verbose"],
            description="Test backend",
            timeout=30,
            env={"KEY": "value"}
        )
        
        assert config.name == "test_backend"
        assert config.command == "python"
        assert config.args == ["script.py", "--verbose"]
        assert config.description == "Test backend"
        assert config.timeout == 30
        assert config.env == {"KEY": "value"}
        assert config.get_full_command() == ["python", "script.py", "--verbose"]
    
    def test_initialization_with_no_args(self):
        """Test initialization with command but no args"""
        config = BackendMCPConfig(
            name="test_backend",
            command="python",
            description="Test backend"
        )
        
        assert config.command == "python"
        assert config.args == []
        assert config.get_full_command() == ["python"]
    
    def test_initialization_with_defaults(self):
        """Test initialization with default values"""
        config = BackendMCPConfig(
            name="test_backend",
            command="python"
        )
        
        assert config.args == []
        assert config.description == "No description"
        assert config.timeout == 30
        assert config.env == {}
    
    def test_default_empty_env(self):
        """Test that env defaults to empty dict when not provided"""
        config = BackendMCPConfig(
            name="test_backend",
            command="python"
            # env not provided - should default to {}
        )
        
        assert config.env == {}


class TestConfigurationManager:
    """Test cases for ConfigurationManager class"""
    
    def test_initialization(self):
        """Test ConfigurationManager initialization"""
        config_manager = ConfigurationManager("test_config.json")
        
        assert config_manager.config_file == Path("test_config.json")
        assert config_manager.backends == {}
    
    def test_load_valid_config(self):
        """Test loading a valid configuration file"""
        config_data = {
            "backends": [
                {
                    "name": "backend1",
                    "command": "python",
                    "args": ["backend1.py"],
                    "description": "Backend 1",
                    "timeout": 20,
                    "env": {"VAR1": "value1"}
                },
                {
                    "name": "backend2",
                    "command": "python",
                    "args": ["backend2.py"],
                    "description": "Backend 2"
                }
            ],
            "security_policy": {
                "backend_security_levels": {
                    "backend1": "public",
                    "backend2": "internal"
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name
        
        try:
            config_manager = ConfigurationManager(temp_file)
            backends = config_manager.load()
            
            assert len(backends) == 2
            assert "backend1" in backends
            assert "backend2" in backends
            
            # Check backend1
            backend1 = backends["backend1"]
            assert backend1.name == "backend1"
            assert backend1.command == "python"
            assert backend1.args == ["backend1.py"]
            assert backend1.get_full_command() == ["python", "backend1.py"]
            assert backend1.description == "Backend 1"
            assert backend1.timeout == 20
            assert backend1.env == {"VAR1": "value1"}
            
            # Check backend2
            backend2 = backends["backend2"]
            assert backend2.name == "backend2"
            assert backend2.command == "python"
            assert backend2.args == ["backend2.py"]
            assert backend2.get_full_command() == ["python", "backend2.py"]
            assert backend2.description == "Backend 2"
            assert backend2.timeout == 30  # default
            assert backend2.env == {}
            
        finally:
            os.unlink(temp_file)
    
    def test_load_empty_backends(self):
        """Test loading configuration with empty backends list"""
        config_data = {
            "backends": [],
            "security_policy": {
                "backend_security_levels": {}
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name
        
        try:
            config_manager = ConfigurationManager(temp_file)
            backends = config_manager.load()
            
            assert len(backends) == 0
            
        finally:
            os.unlink(temp_file)
    
    def test_load_file_not_found(self):
        """Test loading when configuration file doesn't exist"""
        config_manager = ConfigurationManager("non_existent_file.json")
        
        with pytest.raises(FileNotFoundError):
            config_manager.load()
    
    def test_load_invalid_json(self):
        """Test loading invalid JSON file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_file = f.name
        
        try:
            config_manager = ConfigurationManager(temp_file)
            
            with pytest.raises(ConfigurationError) as exc_info:
                config_manager.load()
                
            assert "Invalid JSON" in str(exc_info.value)
                
        finally:
            os.unlink(temp_file)
    
    def test_load_missing_required_fields(self):
        """Test loading configuration with missing required fields"""
        # Missing 'name' field
        config_data = {
            "backends": [
                {
                    "command": "python",
                    "args": ["backend.py"],
                    "description": "Backend"
                }
            ],
            "security_policy": {
                "backend_security_levels": {}
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name
        
        try:
            config_manager = ConfigurationManager(temp_file)
            
            with pytest.raises(ConfigurationError) as exc_info:
                config_manager.load()
                
            assert "name" in str(exc_info.value)
                
        finally:
            os.unlink(temp_file)
    
    def test_load_with_test_config(self):
        """Test loading the actual test configuration file"""
        # This assumes tests/test_config.json exists
        test_config_path = Path(__file__).parent / "test_config.json"
        if test_config_path.exists():
            config_manager = ConfigurationManager(str(test_config_path))
            backends = config_manager.load()
            
            assert len(backends) == 2
            assert "test_backend_1" in backends
            assert "test_backend_2" in backends
            
            # Verify test_backend_1
            backend1 = backends["test_backend_1"]
            assert backend1.command == "echo"
            assert backend1.args == ["backend1"]
            assert backend1.get_full_command() == ["echo", "backend1"]
            assert backend1.timeout == 10
            assert backend1.env == {"TEST_VAR": "value1"}
            
            # Verify test_backend_2
            backend2 = backends["test_backend_2"]
            assert backend2.command == "echo"
            assert backend2.args == ["backend2"]
            assert backend2.get_full_command() == ["echo", "backend2"]
            assert backend2.timeout == 5 