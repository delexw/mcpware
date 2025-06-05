"""
Configuration module for Gateway MCP Server
"""
import json
import logging
import os
from typing import Dict, List, Optional, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BackendMCPConfig:
    """Configuration for a backend MCP server"""
    name: str
    command: Union[str, List[str]]
    description: str
    timeout: int = 30
    env: Optional[Dict[str, str]] = None
    
    def __post_init__(self):
        if self.env is None:
            self.env = {}
        # Ensure command is a list
        if isinstance(self.command, str):
            self.command = [self.command]


class ConfigurationManager:
    """Manages configuration for the Gateway MCP Server"""
    
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.backends = {}
        self.config = {}  # Store full configuration
    
    def load(self) -> Dict[str, BackendMCPConfig]:
        """Load configuration from JSON file"""
        if not os.path.exists(self.config_file):
            error_msg = f"Configuration file not found: {self.config_file}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
            
            # Store full configuration
            self.config = config_data
            
            # Validate security policy is present
            if 'security_policy' not in config_data:
                raise ValueError("Missing required 'security_policy' in configuration")
            
            if not isinstance(config_data['security_policy'], dict):
                raise ValueError("'security_policy' must be a dictionary")
            
            if 'backend_security_levels' not in config_data['security_policy']:
                raise ValueError("Missing required 'backend_security_levels' in security_policy")
            
            # Extract backends
            backends_data = config_data.get('backends', [])
            
            # Validate that all backends have security levels defined
            backend_names = {backend['name'] for backend in backends_data}
            classified_backends = set(config_data['security_policy']['backend_security_levels'].keys())
            
            unclassified = backend_names - classified_backends
            if unclassified:
                raise ValueError(
                    f"The following backends are not classified in security policy: {', '.join(sorted(unclassified))}. "
                    f"Please add them to 'backend_security_levels' with value: public, internal, or sensitive"
                )
            
            backends = {}
            for backend_data in backends_data:
                backend = BackendMCPConfig(
                    name=backend_data['name'],
                    command=backend_data['command'],
                    description=backend_data.get('description', 'No description'),
                    env=backend_data.get('env', {}),
                    timeout=backend_data.get('timeout', 30)
                )
                backends[backend.name] = backend
            
            self.backends = backends
            logger.info(f"Loaded {len(backends)} backend configurations")
            
            return backends
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise
        except KeyError as e:
            logger.error(f"Missing required configuration field: {e}")
            raise
        except ValueError as e:
            logger.error(f"Configuration validation error: {e}")
            raise 