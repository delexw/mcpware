"""
Backend module for Gateway MCP Server
Handles forwarding requests to HTTP-based backend MCP servers
"""
import json
import logging
from typing import Any, Dict, Optional
import httpx
import asyncio
import os
import re

from .config import BackendMCPConfig

logger = logging.getLogger(__name__)


def substitute_env_vars(value: str) -> str:
    """Substitute environment variables in a string"""
    def replace_var(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))
    
    return re.sub(r'\$\{([^}]+)\}', replace_var, value)


class BackendForwarder:
    """Manages forwarding requests to HTTP-based backend MCP servers"""
    
    def __init__(self, backends: list):
        self.backends = {b["name"]: b for b in backends}
        self.clients: Dict[str, httpx.AsyncClient] = {}
        
    async def initialize(self):
        """Initialize HTTP clients for all backends"""
        for name, config in self.backends.items():
            # Process headers with environment variable substitution
            headers = {}
            for key, value in config.get("headers", {}).items():
                headers[key] = substitute_env_vars(value)
            
            self.clients[name] = httpx.AsyncClient(
                timeout=config.get("timeout", 30),
                headers=headers
            )
            
    async def forward_request(self, backend_name: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Forward a request to the specified backend"""
        if backend_name not in self.clients:
            raise ValueError(f"Unknown backend: {backend_name}")
            
        backend_config = self.backends[backend_name]
        client = self.clients[backend_name]
        
        try:
            response = await client.post(
                backend_config["url"],
                json=request_data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error forwarding to {backend_name}: {e}")
            raise
            
    async def close(self):
        """Close all HTTP clients"""
        for client in self.clients.values():
            try:
                await client.aclose()
            except Exception as e:
                logger.error(f"Error closing client: {e}")
            
    async def forward_tool_call(self, backend_name: str, tool_name: str, parameters: Any) -> Any:
        """Forward a tool call to the specified backend (legacy method for compatibility)"""
        if backend_name not in self.clients:
            raise ValueError(f"Unknown backend: {backend_name}")
            
        # Prepare the tool call request
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": parameters
            },
            "id": f"tool-{backend_name}"
        }
        
        response = await self.forward_request(backend_name, request)
        
        if "error" in response:
            raise Exception(f"Backend error: {response['error']}")
            
        return response.get("result")
        
    async def check_backend_health(self, backend_name: str) -> Dict[str, Any]:
        """Check the health of a specific backend"""
        if backend_name not in self.clients:
            return {
                "name": backend_name,
                "status": "unknown",
                "error": "Backend not found"
            }
            
        backend_config = self.backends[backend_name]
        
        try:
            # Send initialize request to test backend
            request_data = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {}
                },
                "id": "health-check"
            }
            
            response = await self.clients[backend_name].post(
                backend_config["url"],
                json=request_data
            )
            
            if response.status_code == 200:
                return {
                    "name": backend_name,
                    "status": "healthy",
                    "url": backend_config.get("url", "stdio"),
                    "info": response.json().get("result", {}).get("serverInfo", {})
                }
            else:
                return {
                    "name": backend_name,
                    "status": "unhealthy",
                    "url": backend_config.get("url", "stdio"),
                    "error": "Invalid response"
                }
                
        except Exception as e:
            logger.error(f"Health check failed for {backend_name}: {e}")
            return {
                "name": backend_name,
                "status": "unhealthy",
                "url": backend_config.get("url", "stdio"),
                "error": str(e)
            }
            
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
            import json
            return json.dumps(result, indent=2)
        
        # Return string representation for other types
        return str(result) 