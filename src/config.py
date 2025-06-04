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
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.backends: Dict[str, BackendMCPConfig] = {}
        
    def load(self) -> Dict[str, BackendMCPConfig]:
        """Load configuration from file"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                
            backends = {}
            for backend_config in config.get('backends', []):
                backend = BackendMCPConfig(
                    name=backend_config['name'],
                    command=backend_config['command'],
                    description=backend_config['description'],
                    timeout=backend_config.get('timeout', 30),
                    env=backend_config.get('env', {})
                )
                backends[backend.name] = backend
                
            logger.info(f"Loaded {len(backends)} backend configurations")
            return backends
            
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_file}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise
        except KeyError as e:
            logger.error(f"Missing required configuration field: {e}")
            raise 