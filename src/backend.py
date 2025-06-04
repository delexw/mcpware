"""
Backend module for Gateway MCP Server
Handles forwarding requests to stdio-based backend MCP servers
"""
import json
import logging
import asyncio
import subprocess
import os
import re
from typing import Any, Dict, Optional
from asyncio import StreamReader, StreamWriter

logger = logging.getLogger(__name__)


def substitute_env_vars(value: str) -> str:
    """Substitute environment variables in a string"""
    def replace_var(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))
    
    return re.sub(r'\$\{([^}]+)\}', replace_var, value)


class StdioBackend:
    """Manages communication with a single stdio-based MCP backend"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.reader: Optional[StreamReader] = None
        self.writer: Optional[StreamWriter] = None
        self.read_task: Optional[asyncio.Task] = None
        self.pending_requests: Dict[Any, asyncio.Future] = {}
        self.next_id = 1
        
    async def start(self):
        """Start the backend process"""
        command = self.config.get("command", [])
        if isinstance(command, str):
            command = [command]
        
        # Substitute environment variables in command
        command = [substitute_env_vars(part) for part in command]
        
        # Prepare environment
        env = os.environ.copy()
        for key, value in self.config.get("env", {}).items():
            env[key] = substitute_env_vars(value)
        
        logger.info(f"Starting backend {self.name} with command: {command}")
        
        # Start the process
        self.process = await asyncio.create_subprocess_exec(
            *command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        
        # Start reading from the backend
        self.read_task = asyncio.create_task(self._read_loop())
        
    async def _read_loop(self):
        """Read responses from the backend"""
        try:
            while self.process and self.process.stdout:
                line = await self.process.stdout.readline()
                if not line:
                    break
                    
                try:
                    response = json.loads(line.decode().strip())
                    request_id = response.get("id")
                    
                    if request_id in self.pending_requests:
                        future = self.pending_requests.pop(request_id)
                        future.set_result(response)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from backend {self.name}: {line}")
                except Exception as e:
                    logger.error(f"Error processing response from {self.name}: {e}")
                    
        except Exception as e:
            logger.error(f"Read loop error for {self.name}: {e}")
            
    async def send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to the backend and wait for response"""
        if not self.process or not self.process.stdin:
            raise RuntimeError(f"Backend {self.name} is not running")
        
        # Assign ID if not present
        if "id" not in request:
            request["id"] = self.next_id
            self.next_id += 1
        
        request_id = request["id"]
        
        # Create future for the response
        future = asyncio.Future()
        self.pending_requests[request_id] = future
        
        try:
            # Send the request
            request_line = json.dumps(request) + "\n"
            self.process.stdin.write(request_line.encode())
            await self.process.stdin.drain()
            
            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=self.config.get("timeout", 30))
            return response
            
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            raise TimeoutError(f"Request to backend {self.name} timed out")
        except Exception as e:
            self.pending_requests.pop(request_id, None)
            raise
            
    async def stop(self):
        """Stop the backend process"""
        if self.read_task:
            self.read_task.cancel()
            
        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()


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
            import json
            return json.dumps(result, indent=2)
        
        # Return string representation for other types
        return str(result) 