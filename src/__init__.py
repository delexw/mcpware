"""
mcpware Package
Main package initialization
"""
from .config import ConfigurationManager, BackendMCPConfig
from .utils import substitute_env_vars
from .stdio_backend import StdioBackend
from .backend_forwarder import BackendForwarder
from .mcp_protocol_handler import MCPProtocolHandler
from .jsonrpc_handler import JSONRPCHandler
# Keep backend and protocol imports for backward compatibility
from .backend import *
from .protocol import *

__all__ = [
    'ConfigurationManager',
    'BackendMCPConfig',
    'substitute_env_vars',
    'StdioBackend',
    'BackendForwarder',
    'MCPProtocolHandler',
    'JSONRPCHandler'
] 