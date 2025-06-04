"""
Backend module for Gateway MCP Server
Handles forwarding requests to stdio-based backend MCP servers

This module maintains backward compatibility by re-exporting classes
that have been refactored into separate modules.
"""
# Import for backward compatibility
from .utils import substitute_env_vars
from .stdio_backend import StdioBackend
from .backend_forwarder import BackendForwarder

# Re-export all classes and functions
__all__ = [
    'substitute_env_vars',
    'StdioBackend', 
    'BackendForwarder'
] 