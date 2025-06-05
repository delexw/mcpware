"""
StdioBackend module for mcpware
Manages communication with a single stdio-based MCP backend
"""
import json
import logging
import asyncio
import subprocess
import os
import re
from typing import Any, Dict, Optional, List
from asyncio import StreamReader, StreamWriter

from .utils import substitute_env_vars
from .config import BackendMCPConfig

logger = logging.getLogger(__name__)


class StdioBackend:
    """Manages communication with a single stdio-based MCP backend"""
    
    def __init__(self, name: str, config: BackendMCPConfig):
        self.name = name
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.reader: Optional[StreamReader] = None
        self.writer: Optional[StreamWriter] = None
        self.read_task: Optional[asyncio.Task] = None
        self.stderr_task: Optional[asyncio.Task] = None
        self.pending_requests: Dict[Any, asyncio.Future] = {}
        self.next_id = 1
        
    def _prepare_command(self) -> List[str]:
        """Prepare the command for execution"""
        return self.config.get_full_command()
    
    def _prepare_environment(self) -> Dict[str, str]:
        """Prepare environment variables with substitution"""
        env = os.environ.copy()
        unsubstituted_vars = []
        
        for key, value in self.config.env.items():
            substituted_value = substitute_env_vars(value)
            # Check if substitution failed (placeholder remains)
            if re.search(r'\$\{[^}]+\}', substituted_value):
                var_matches = re.findall(r'\$\{([^}]+)\}', substituted_value)
                unsubstituted_vars.extend(var_matches)
            env[key] = substituted_value
        
        # Check for any unsubstituted variables in env section
        if unsubstituted_vars:
            error_msg = f"Backend {self.name} requires environment variables that are not set: {', '.join(set(unsubstituted_vars))}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
            
        return env
    
    async def start(self):
        """Start the backend process"""
        command = self._prepare_command()
        env = self._prepare_environment()
        
        logger.info(f"Starting backend {self.name}")
        logger.info(f"  Command: {' '.join(command)}")
        logger.info(f"  Working directory: {os.getcwd()}")
        
        # Log environment variables that were set/modified
        env_diff = {k: v for k, v in env.items() if k not in os.environ or os.environ[k] != v}
        if env_diff:
            logger.info(f"  Modified environment variables: {list(env_diff.keys())}")
        
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
        
        # Start monitoring stderr for debugging
        self.stderr_task = asyncio.create_task(self._stderr_monitor())
        
        logger.info(f"Backend {self.name} process started with PID: {self.process.pid}")
        
        # Give the process a moment to start up
        await asyncio.sleep(0.5)
        
        # Check if the process is still running
        if self.process.returncode is not None:
            logger.error(f"Backend {self.name} exited immediately with code: {self.process.returncode}")
            # Try to get any stderr output
            if self.process.stderr:
                try:
                    stderr_output = await asyncio.wait_for(self.process.stderr.read(), timeout=1)
                    if stderr_output:
                        logger.error(f"Backend {self.name} stderr on exit: {stderr_output.decode()}")
                except:
                    pass
            raise RuntimeError(f"Backend {self.name} failed to start (exit code: {self.process.returncode})")
        else:
            logger.info(f"Backend {self.name} is running")
        
    async def _read_loop(self):
        """Read responses from the backend"""
        logger.info(f"Starting read loop for backend {self.name}")
        try:
            while self.process and self.process.stdout:
                logger.info(f"Gateway waiting for data from backend {self.name}...")
                line = await self.process.stdout.readline()
                if not line:
                    logger.warning(f"Backend {self.name} stdout closed (no more data)")
                    break
                    
                logger.info(f"Gateway received data from backend {self.name}: {line}")
                    
                try:
                    response = json.loads(line.decode().strip())
                    request_id = response.get("id")
                    
                    # Log all responses for debugging
                    logger.info(f"Gateway received response from backend {self.name}: {response}")
                    
                    if request_id in self.pending_requests:
                        future = self.pending_requests.pop(request_id)
                        future.set_result(response)
                    else:
                        # Log unexpected responses that don't match any pending request
                        logger.warning(f"Gateway received unexpected response from backend {self.name} with id={request_id}: {response}")
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from backend {self.name}: {line}")
                except Exception as e:
                    logger.error(f"Error processing response from {self.name}: {e}")
                    
        except Exception as e:
            logger.error(f"Read loop error for {self.name}: {e}")
        finally:
            logger.info(f"Read loop ended for backend {self.name}")
            
    async def _stderr_monitor(self):
        """Monitor stderr output for debugging"""
        if not self.process or not self.process.stderr:
            return
            
        try:
            while True:
                line = await self.process.stderr.readline()
                if not line:
                    break
                    
                stderr_msg = line.decode().strip()
                if stderr_msg:
                    logger.warning(f"Backend {self.name} stderr: {stderr_msg}")
                    
        except Exception as e:
            logger.error(f"Error monitoring stderr for {self.name}: {e}")
            
    async def send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to the backend and wait for response"""
        if not self.process or not self.process.stdin:
            raise RuntimeError(f"Backend {self.name} is not running")
        
        # Check if process is still alive
        if self.process.returncode is not None:
            logger.error(f"Backend {self.name} process has exited with code: {self.process.returncode}")
            raise RuntimeError(f"Backend {self.name} process has exited unexpectedly")
        
        # Assign ID if not present
        if "id" not in request:
            request["id"] = self.next_id
            self.next_id += 1
        
        request_id = request["id"]
        method = request.get("method", "unknown")
        
        logger.info(f"Gateway sending request to backend {self.name} - id: {request_id}, method: {method}")
        
        # Create future for the response
        future = asyncio.Future()
        self.pending_requests[request_id] = future
        
        try:
            # Send the request
            request_line = json.dumps(request) + "\n"
            self.process.stdin.write(request_line.encode())
            await self.process.stdin.drain()
            
            # Wait for response with timeout
            timeout = self.config.timeout
            logger.info(f"Gateway waiting for response from backend {self.name} - id: {request_id} (timeout: {timeout}s)")
            response = await asyncio.wait_for(future, timeout=timeout)
            logger.info(f"Gateway received response from backend {self.name} - id: {request_id}")
            return response
            
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            logger.error(f"Backend {self.name} request {request_id} ({method}) timed out after {timeout}s")
            logger.error(f"  Pending requests: {list(self.pending_requests.keys())}")
            raise TimeoutError(f"Request to backend {self.name} timed out")
        except Exception as e:
            self.pending_requests.pop(request_id, None)
            logger.error(f"Backend {self.name} request {request_id} failed: {e}")
            raise
            
    async def stop(self):
        """Stop the backend process"""
        if self.read_task:
            self.read_task.cancel()
            
        if self.stderr_task:
            self.stderr_task.cancel()
            
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except ProcessLookupError:
                # Process already terminated
                pass
            except asyncio.TimeoutError:
                # Force kill if terminate didn't work
                try:
                    self.process.kill()
                    await self.process.wait()
                except ProcessLookupError:
                    # Process already terminated
                    pass 