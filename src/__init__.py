"""
Gateway MCP Server
Routes tool calls to HTTP-based MCP backend servers in Docker
"""

from .config import ConfigurationManager, BackendMCPConfig
from .backend import BackendForwarder
from .protocol import MCPProtocolHandler, JSONRPCHandler

__version__ = "1.0.0"

__all__ = [
    "ConfigurationManager",
    "BackendMCPConfig", 
    "BackendForwarder",
    "MCPProtocolHandler",
    "JSONRPCHandler"
] 