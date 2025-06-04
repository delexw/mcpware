"""
StdioBackend module for Gateway MCP Server
Manages communication with a single stdio-based MCP backend
"""
import json
import logging
import asyncio
import subprocess
import os
from typing import Any, Dict, Optional
from asyncio import StreamReader, StreamWriter

from .utils import substitute_env_vars

logger = logging.getLogger(__name__)


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