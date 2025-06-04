"""
MCP Protocol module for Gateway MCP Server
Handles MCP protocol messages and responses

This module maintains backward compatibility by re-exporting classes
that have been refactored into separate modules.
"""
# Import for backward compatibility
from .mcp_protocol_handler import MCPProtocolHandler
from .jsonrpc_handler import JSONRPCHandler

# Re-export all classes
__all__ = [
    'MCPProtocolHandler',
    'JSONRPCHandler'
] 