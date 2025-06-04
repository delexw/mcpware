"""
JSONRPCHandler module for Gateway MCP Server
Handles JSON-RPC protocol wrapping for MCP messages
"""
import logging
from typing import Dict, Any, Optional

from .mcp_protocol_handler import MCPProtocolHandler

logger = logging.getLogger(__name__)


class JSONRPCHandler:
    """Handles JSON-RPC protocol wrapping"""
    
    def __init__(self, protocol_handler: MCPProtocolHandler):
        self.protocol_handler = protocol_handler
        
    async def handle_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming JSON-RPC request"""
        method = data.get("method", "")
        params = data.get("params", {})
        
        # Check if this is a notification (no id field at all)
        # Note: id: null is still a request, not a notification
        if "id" not in data:
            # This is a notification - no response should be sent
            logger.debug(f"Received notification: {method}")
            
            # Handle known notifications
            if method == "notifications/cancelled":
                # Log the cancellation but don't do anything else
                logger.debug(f"Received cancellation notification: {params}")
            # Add other notification handlers here as needed
            
            return None
        
        # This is a request (has id field, even if null)
        request_id = data.get("id")
        
        try:
            # Route based on method
            if method == "initialize":
                response = await self.protocol_handler.handle_initialize(params)
            elif method == "tools/list":
                response = await self.protocol_handler.handle_list_tools(params)
            elif method == "tools/call":
                response = await self.protocol_handler.handle_tool_call(params)
            elif method == "resources/list":
                response = await self.protocol_handler.handle_list_resources()
            elif method == "resources/read":
                response = await self.protocol_handler.handle_read_resource(params)
            elif method == "prompts/list":
                response = await self.protocol_handler.handle_list_prompts()
            elif method == "prompts/get":
                response = await self.protocol_handler.handle_get_prompt(params)
            elif method == "notifications/cancelled":
                # This shouldn't happen since we handle it above, but just in case
                return self._create_error_response(
                    request_id,
                    -32601,
                    f"Method {method} is a notification and should not have an id"
                )
            else:
                return self._create_error_response(
                    request_id,
                    -32601,
                    f"Method not found: {method}"
                )
            
            return self._create_success_response(request_id, response)
            
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            return self._create_error_response(
                request_id,
                -32603,
                "Internal error",
                str(e)
            )
    
    def _create_success_response(self, request_id: Any, result: Any) -> Dict[str, Any]:
        """Create a successful JSON-RPC response"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
    
    def _create_error_response(
        self,
        request_id: Any,
        code: int,
        message: str,
        data: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create an error JSON-RPC response"""
        error = {
            "code": code,
            "message": message
        }
        
        if data:
            error["data"] = data
            
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": error
        } 