"""
Configuration module for mcpware
"""
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Union

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Base exception for configuration errors"""
    pass


class SecurityPolicyError(ConfigurationError):
    """Exception for security policy configuration errors"""
    pass


@dataclass
class BackendMCPConfig:
    """Configuration for a backend MCP server"""
    name: str
    command: str
    args: List[str] = field(default_factory=list)
    description: str = "No description"
    timeout: int = 30
    env: Dict[str, str] = field(default_factory=dict)
    
    def get_full_command(self) -> List[str]:
        """Get the full command as a list (command + args)"""
        return [self.command] + self.args


class ConfigurationManager:
    """Manages configuration for the mcpware"""
    
    def __init__(self, config_file: Union[str, Path]):
        self.config_file = Path(config_file)
        self.backends: Dict[str, BackendMCPConfig] = {}
        self.config: Dict = {}  # Store full configuration
    
    def load(self) -> Dict[str, BackendMCPConfig]:
        """Load configuration from JSON file"""
        if not self.config_file.exists():
            error_msg = f"Configuration file not found: {self.config_file}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            with self.config_file.open('r') as f:
                config_data = json.load(f)
            
            # Store full configuration
            self.config = config_data
            
            # Extract and validate backends
            backends_data = config_data.get('backends', {})
            backends = self._create_backends(backends_data)
            
            self.backends = backends
            logger.info(f"Loaded {len(backends)} backend configurations")
            
            return backends
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise ConfigurationError(f"Invalid JSON: {e}") from e
        except (KeyError, ValueError) as e:
            logger.error(f"Configuration error: {e}")
            raise ConfigurationError(str(e)) from e
    
    def _create_backends(self, backends_data: Dict[str, Dict]) -> Dict[str, BackendMCPConfig]:
        """Create backend configurations"""
        # Create backend configurations using dictionary comprehension
        return {
            name: BackendMCPConfig(
                name=name,
                command=backend_data['command'],
                args=backend_data.get('args', []),
                description=backend_data.get('description', 'No description'),
                env=backend_data.get('env', {}),
                timeout=backend_data.get('timeout', 30)
            )
            for name, backend_data in backends_data.items()
        } 