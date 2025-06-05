"""
BackendForwarder module for Gateway MCP Server
Manages forwarding requests to multiple stdio-based backend MCP servers
"""
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from .stdio_backend import StdioBackend

logger = logging.getLogger(__name__)


class BackendStatus(Enum):
    """Backend health status"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class BackendHealthResult:
    """Result of a backend health check"""
    name: str
    status: BackendStatus
    error: Optional[str] = None
    command: Optional[List[str]] = None
    info: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            "name": self.name,
            "status": self.status.value
        }
        if self.error:
            result["error"] = self.error
        if self.command:
            result["command"] = self.command
        if self.info:
            result["info"] = self.info
        return result


class BackendForwarder:
    """Manages forwarding requests to stdio-based backend MCP servers"""
    
    def __init__(self, backends: List[Dict[str, Any]]):
        self.backend_configs = {b["name"]: b for b in backends}
        self.backends: Dict[str, StdioBackend] = {}
        
    async def initialize(self) -> None:
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
            return BackendHealthResult(
                name=backend_name,
                status=BackendStatus.UNKNOWN,
                error="Backend not found"
            ).to_dict()
            
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
            
            if result := response.get("result"):
                return BackendHealthResult(
                    name=backend_name,
                    status=BackendStatus.HEALTHY,
                    command=backend.config.get("command"),
                    info=result.get("serverInfo", {})
                ).to_dict()
            
            return BackendHealthResult(
                name=backend_name,
                status=BackendStatus.UNHEALTHY,
                error="Invalid response"
            ).to_dict()
                
        except Exception as e:
            logger.error(f"Health check failed for {backend_name}: {e}")
            return BackendHealthResult(
                name=backend_name,
                status=BackendStatus.UNHEALTHY,
                error=str(e)
            ).to_dict()
            
    async def close(self) -> None:
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
                contents = [
                    item.get("text", "")
                    for item in result["content"]
                    if item.get("type") == "text"
                ]
                return "\n".join(contents)
            
            # Return JSON for other dict responses
            return json.dumps(result, indent=2)
        
        # Return string representation for other types
        return str(result) 