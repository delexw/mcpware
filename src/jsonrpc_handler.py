"""
JSONRPCHandler module for mcpware
Handles JSON-RPC protocol wrapping for MCP messages
"""
import logging
from typing import Any, Callable, Dict, Optional

from .mcp_protocol_handler import MCPProtocolHandler

logger = logging.getLogger(__name__)


class JSONRPCHandler:
    """Handles JSON-RPC protocol wrapping"""
    
    def __init__(self, protocol_handler: MCPProtocolHandler):
        self.protocol_handler = protocol_handler
        self._method_handlers = self._setup_method_handlers()
        
    def _setup_method_handlers(self) -> Dict[str, Callable]:
        """Setup mapping of methods to handlers"""
        return {
            "initialize": self.protocol_handler.handle_initialize,
            "tools/list": self.protocol_handler.handle_list_tools,
            "tools/call": self.protocol_handler.handle_tool_call,
            "resources/list": lambda _: self.protocol_handler.handle_list_resources(),
            "resources/read": self.protocol_handler.handle_read_resource,
            "prompts/list": lambda _: self.protocol_handler.handle_list_prompts(),
            "prompts/get": self.protocol_handler.handle_get_prompt,
        }
        
    async def handle_request(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle incoming JSON-RPC request"""
        method = data.get("method", "")
        params = data.get("params", {})
        
        # Check if this is a notification (no id field)
        if "id" not in data:
            await self._handle_notification(method, params)
            return None
        
        # This is a request (has id field)
        request_id = data.get("id")
        
        try:
            # Use method handler dispatch
            if handler := self._method_handlers.get(method):
                # Handle methods that don't take params
                if method in ("resources/list", "prompts/list"):
                    response = await handler(params)
                else:
                    response = await handler(params)
                
                return self._create_success_response(request_id, response)
            
            # Check for notification methods that shouldn't have an id
            if method == "notifications/cancelled":
                return self._create_error_response(
                    request_id,
                    -32601,
                    f"Method {method} is a notification and should not have an id"
                )
            
            # Method not found
            return self._create_error_response(
                request_id,
                -32601,
                f"Method not found: {method}"
            )
            
        except Exception as e:
            logger.error(f"Error handling request: {e}", exc_info=True)
            return self._create_error_response(
                request_id,
                -32603,
                "Internal error",
                str(e)
            )
    
    async def _handle_notification(self, method: str, params: Dict[str, Any]) -> None:
        """Handle notifications (requests without id)"""
        logger.info(f"Received notification: {method}")
        
        match method:
            case "notifications/initialized":
                # Forward initialized notification to all backends
                logger.info("Forwarding initialized notification to all backends")
                await self.protocol_handler.handle_initialized_notification()
            case "notifications/cancelled":
                logger.info(f"Received cancellation notification: {params}")
            case _:
                logger.info(f"Unhandled notification: {method}")
    
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
        error: Dict[str, Any] = {
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