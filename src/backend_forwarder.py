"""
BackendForwarder module for Gateway MCP Server
Manages forwarding requests to multiple stdio-based backend MCP servers
"""
import json
import logging
from typing import Any, Dict

from .stdio_backend import StdioBackend

logger = logging.getLogger(__name__)


class BackendForwarder:
    """Manages forwarding requests to stdio-based backend MCP servers"""
    
    def __init__(self, backends: list):
        self.backend_configs = {b["name"]: b for b in backends}
        self.backends: Dict[str, StdioBackend] = {}
        
    async def initialize(self):
        """Initialize and start all backend processes"""
        for name, config in self.backend_configs.items():
            backend = StdioBackend(name, config)
            self.backends[name] = backend
            
            try:
                await backend.start()
                logger.info(f"Started backend: {name}")
            except Exception as e:
                logger.error(f"Failed to start backend {name}: {e}")
                
    async def forward_request(self, backend_name: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Forward a request to the specified backend"""
        if backend_name not in self.backends:
            raise ValueError(f"Unknown backend: {backend_name}")
            
        backend = self.backends[backend_name]
        return await backend.send_request(request_data)
        
    async def forward_tool_call(self, backend_name: str, tool_name: str, parameters: Any) -> Any:
        """Forward a tool call to the specified backend"""
        if backend_name not in self.backends:
            raise ValueError(f"Unknown backend: {backend_name}")
            
        # Prepare the tool call request
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": parameters
            }
        }
        
        response = await self.forward_request(backend_name, request)
        
        if "error" in response:
            raise Exception(f"Backend error: {response['error']}")
            
        return response.get("result")
        
    async def check_backend_health(self, backend_name: str) -> Dict[str, Any]:
        """Check the health of a specific backend"""
        if backend_name not in self.backends:
            return {
                "name": backend_name,
                "status": "unknown",
                "error": "Backend not found"
            }
            
        backend = self.backends[backend_name]
        
        try:
            # Send initialize request to test backend
            request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {}
                }
            }
            
            response = await backend.send_request(request)
            
            if response.get("result"):
                return {
                    "name": backend_name,
                    "status": "healthy",
                    "command": backend.config.get("command"),
                    "info": response.get("result", {}).get("serverInfo", {})
                }
            else:
                return {
                    "name": backend_name,
                    "status": "unhealthy",
                    "error": "Invalid response"
                }
                
        except Exception as e:
            logger.error(f"Health check failed for {backend_name}: {e}")
            return {
                "name": backend_name,
                "status": "unhealthy",
                "error": str(e)
            }
            
    async def close(self):
        """Stop all backend processes"""
        for backend in self.backends.values():
            try:
                await backend.stop()
            except Exception as e:
                logger.error(f"Error stopping backend {backend.name}: {e}")
                
    def _parse_backend_response(self, result: Any) -> str:
        """Parse response from backend MCP server"""
        if isinstance(result, dict):
            # Handle MCP tool response format
            if "content" in result and isinstance(result["content"], list):
                contents = []
                for item in result["content"]:
                    if item.get("type") == "text":
                        contents.append(item.get("text", ""))
                return "\n".join(contents)
            
            # Return JSON for other dict responses
            return json.dumps(result, indent=2)
        
        # Return string representation for other types
        return str(result) 