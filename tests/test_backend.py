"""
Unit tests for backend module
"""
import json
import pytest
import asyncio
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from src.backend import substitute_env_vars, StdioBackend, BackendForwarder
from src.config import BackendMCPConfig


class TestSubstituteEnvVars:
    """Test cases for substitute_env_vars function"""
    
    def test_simple_substitution(self):
        """Test simple environment variable substitution"""
        os.environ["TEST_VAR"] = "test_value"
        result = substitute_env_vars("${TEST_VAR}")
        assert result == "test_value"
    
    def test_substitution_in_string(self):
        """Test substitution within a string"""
        os.environ["HOME"] = "/home/user"
        result = substitute_env_vars("path: ${HOME}/documents")
        assert result == "path: /home/user/documents"
    
    def test_multiple_substitutions(self):
        """Test multiple substitutions in one string"""
        os.environ["VAR1"] = "value1"
        os.environ["VAR2"] = "value2"
        result = substitute_env_vars("${VAR1} and ${VAR2}")
        assert result == "value1 and value2"
    
    def test_nonexistent_variable(self):
        """Test behavior with non-existent variable (should keep original)"""
        result = substitute_env_vars("${NONEXISTENT_VAR}")
        assert result == "${NONEXISTENT_VAR}"
    
    def test_no_substitution_needed(self):
        """Test string without variables"""
        result = substitute_env_vars("no variables here")
        assert result == "no variables here"


class TestStdioBackend:
    """Test cases for StdioBackend class"""
    
    @pytest.fixture
    def backend_config(self):
        """Fixture for backend configuration"""
        return BackendMCPConfig(
            name="test_backend",
            command="echo",
            args=["test"],
            timeout=30,
            env={"TEST_ENV": "value"}
        )
    
    @pytest.fixture
    def backend(self, backend_config):
        """Fixture for StdioBackend instance"""
        return StdioBackend("test_backend", backend_config)
    
    def test_initialization(self, backend):
        """Test StdioBackend initialization"""
        assert backend.name == "test_backend"
        assert backend.config.command == "echo"
        assert backend.config.args == ["test"]
        assert backend.config.get_full_command() == ["echo", "test"]
        assert backend.process is None
        assert backend.reader is None
        assert backend.writer is None
        assert backend.read_task is None
        assert backend.pending_requests == {}
        assert backend.next_id == 1
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_start(self, mock_subprocess, backend):
        """Test starting the backend process"""
        # Mock the subprocess
        mock_process = AsyncMock()
        mock_process.returncode = None  # Process is still running
        mock_process.pid = 12345  # Mock PID
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.stdout.readline = AsyncMock(return_value=b'')
        mock_process.stderr.readline = AsyncMock(return_value=b'')
        mock_process.stderr.read = AsyncMock(return_value=b'')  # For error handling
        mock_subprocess.return_value = mock_process
        
        await backend.start()
        
        # Verify subprocess was created with correct parameters
        mock_subprocess.assert_called_once_with(
            "echo", "test",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=unittest.mock.ANY,
            limit=10485760  # 10MB limit we added to fix buffer overflow
        )
        
        assert backend.process == mock_process
        assert backend.read_task is not None
        assert backend.stderr_task is not None
        
        # Clean up
        backend.read_task.cancel()
        try:
            await backend.read_task
        except asyncio.CancelledError:
            pass
        backend.stderr_task.cancel()
        try:
            await backend.stderr_task
        except asyncio.CancelledError:
            pass
    
    @pytest.mark.asyncio
    async def test_send_request_not_running(self, backend):
        """Test sending request when backend is not running"""
        with pytest.raises(RuntimeError, match="Backend test_backend is not running"):
            await backend.send_request({"method": "test"})
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_send_request_with_response(self, mock_subprocess, backend):
        """Test sending request and receiving response"""
        # Mock the subprocess
        mock_process = AsyncMock()
        mock_process.returncode = None  # Process is still running
        mock_process.pid = 12345  # Mock PID
        mock_process.stdin = Mock()  # Use regular Mock for stdin
        mock_process.stdin.write = Mock()  # Regular sync method
        mock_process.stdin.drain = AsyncMock()  # Async method
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        
        # Mock response
        response = {"jsonrpc": "2.0", "id": 1, "result": "test_result"}
        response_bytes = json.dumps(response).encode() + b'\n'
        
        # Create a flag to track if request has been sent
        request_sent = asyncio.Event()
        
        async def mock_readline():
            # First call waits for request to be sent
            if not mock_process.stdout.readline.call_count > 1:
                await request_sent.wait()
                await asyncio.sleep(0.01)  # Small delay
                return response_bytes
            # Second call returns EOF
            return b''
        
        mock_process.stdout.readline = AsyncMock(side_effect=mock_readline)
        mock_process.stderr.readline = AsyncMock(return_value=b'')  # No stderr output
        mock_process.stderr.read = AsyncMock(return_value=b'')  # For error handling
        mock_subprocess.return_value = mock_process
        
        # Override drain to signal that request was sent
        original_drain = mock_process.stdin.drain
        async def mock_drain():
            await original_drain()
            request_sent.set()
        mock_process.stdin.drain = mock_drain
        
        await backend.start()
        
        # Send request
        request = {"id": 1, "method": "test_method", "params": {}}
        result = await backend.send_request(request)
        
        assert result == response
        assert mock_process.stdin.write.called
        
        # Clean up
        backend.read_task.cancel()
        try:
            await backend.read_task
        except asyncio.CancelledError:
            pass
        backend.stderr_task.cancel()
        try:
            await backend.stderr_task
        except asyncio.CancelledError:
            pass
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_send_request_timeout(self, mock_subprocess):
        """Test request timeout handling"""
        # Create backend with short timeout
        config = BackendMCPConfig(
            name="test_backend",
            command="echo",
            args=["test"],
            timeout=0.1  # Short timeout
        )
        backend = StdioBackend("test_backend", config)
        
        # Mock the subprocess
        mock_process = AsyncMock()
        mock_process.returncode = None  # Process is still running
        mock_process.pid = 12345  # Mock PID
        mock_process.stdin = Mock()  # Use regular Mock for stdin
        mock_process.stdin.write = Mock()  # Regular sync method
        mock_process.stdin.drain = AsyncMock()  # Async method
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.stdout.readline = AsyncMock(return_value=b'')  # No response
        mock_process.stderr.readline = AsyncMock(return_value=b'')  # No stderr output
        mock_process.stderr.read = AsyncMock(return_value=b'')  # For error handling
        mock_subprocess.return_value = mock_process
        
        await backend.start()
        
        # Send request that will timeout
        request = {"method": "test_method", "params": {}}
        with pytest.raises(TimeoutError, match="Request to backend test_backend timed out"):
            await backend.send_request(request)
        
        # Clean up
        backend.read_task.cancel()
        try:
            await backend.read_task
        except asyncio.CancelledError:
            pass
        backend.stderr_task.cancel()
        try:
            await backend.stderr_task
        except asyncio.CancelledError:
            pass
    
    @pytest.mark.asyncio
    async def test_start_with_missing_env_vars(self):
        """Test that start fails when env vars are missing"""
        # Remove any existing env vars
        test_vars = ["TEST_VAR_1", "TEST_VAR_2"]
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]
        
        config = BackendMCPConfig(
            name="test",
            command="echo",
            args=["test"],
            env={
                "TEST_VAR_1": "${TEST_VAR_1}",
                "TEST_VAR_2": "${TEST_VAR_2}"
            },
            timeout=30
        )
        backend = StdioBackend("test", config)
        
        with pytest.raises(RuntimeError) as exc_info:
            await backend.start()
        
        error_msg = str(exc_info.value)
        assert "requires environment variables that are not set" in error_msg
        assert "TEST_VAR_1" in error_msg
        assert "TEST_VAR_2" in error_msg
    
    @pytest.mark.asyncio
    async def test_stop(self, backend):
        """Test stopping the backend process"""
        # Mock process with stdin
        backend.process = AsyncMock()
        backend.process.stdin = AsyncMock()
        backend.process.stdin.is_closing = Mock(return_value=False)
        backend.process.stdin.close = Mock()
        backend.process.stdin.wait_closed = AsyncMock()
        
        # Mock wait() to timeout twice (stdin close and terminate), then succeed on kill
        wait_call_count = 0
        async def mock_wait():
            nonlocal wait_call_count
            wait_call_count += 1
            if wait_call_count <= 2:  # First two calls timeout
                raise asyncio.TimeoutError()
            return 0  # Third call (after kill) succeeds
        
        backend.process.wait = mock_wait
        backend.process.terminate = Mock()
        backend.process.kill = Mock()
        backend.read_task = asyncio.create_task(asyncio.sleep(10))
        backend.stderr_task = asyncio.create_task(asyncio.sleep(10))
        
        await backend.stop()
        
        # Verify stdin was closed first (MCP spec)
        assert backend.process.stdin.close.called
        # Verify terminate was called after stdin close timeout
        assert backend.process.terminate.called
        # Verify kill was called after terminate timeout
        assert backend.process.kill.called
        # Give a bit of time for task cancellation to propagate
        await asyncio.sleep(0.1)
        # Tasks should be cancelled after stop
        assert backend.read_task.cancelled()
        assert backend.stderr_task.cancelled()


class TestBackendForwarder:
    """Test cases for BackendForwarder class"""
    
    @pytest.fixture
    def backend_configs(self):
        """Fixture for backend configurations"""
        return [
            BackendMCPConfig(
                name="backend1",
                command="echo",
                args=["backend1"],
                description="Backend 1",
                timeout=30
            ),
            BackendMCPConfig(
                name="backend2",
                command="echo",
                args=["backend2"],
                description="Backend 2",
                timeout=20
            )
        ]
    
    @pytest.fixture
    def forwarder(self, backend_configs):
        """Fixture for BackendForwarder instance"""
        return BackendForwarder(backend_configs)
    
    def test_initialization(self, forwarder):
        """Test BackendForwarder initialization"""
        assert len(forwarder.backend_configs) == 2
        assert "backend1" in forwarder.backend_configs
        assert "backend2" in forwarder.backend_configs
        assert forwarder.backends == {}
    
    @pytest.mark.asyncio
    @patch('src.backend_forwarder.StdioBackend')
    async def test_initialize(self, mock_stdio_backend, forwarder):
        """Test initializing all backends"""
        # Mock StdioBackend instances
        mock_backend1 = AsyncMock()
        mock_backend2 = AsyncMock()
        mock_stdio_backend.side_effect = [mock_backend1, mock_backend2]
        
        await forwarder.initialize()
        
        assert len(forwarder.backends) == 2
        assert mock_backend1.start.called
        assert mock_backend2.start.called
    
    @pytest.mark.asyncio
    async def test_forward_request_unknown_backend(self, forwarder):
        """Test forwarding request to unknown backend"""
        with pytest.raises(ValueError, match="Unknown backend: nonexistent"):
            await forwarder.forward_request("nonexistent", {"method": "test"})
    
    @pytest.mark.asyncio
    async def test_forward_request(self, forwarder):
        """Test forwarding request to backend"""
        # Mock backend
        mock_backend = AsyncMock()
        mock_backend.send_request = AsyncMock(return_value={"result": "success"})
        forwarder.backends["backend1"] = mock_backend
        
        request = {"method": "test", "params": {}}
        result = await forwarder.forward_request("backend1", request)
        
        assert result == {"result": "success"}
        mock_backend.send_request.assert_called_once_with(request)
    
    @pytest.mark.asyncio
    async def test_forward_tool_call(self, forwarder):
        """Test forwarding tool call to backend"""
        # Mock backend
        mock_backend = AsyncMock()
        mock_backend.send_request = AsyncMock(
            return_value={"jsonrpc": "2.0", "result": "tool_result"}
        )
        forwarder.backends["backend1"] = mock_backend
        
        result = await forwarder.forward_tool_call(
            "backend1", "test_tool", {"param": "value"}
        )
        
        assert result == "tool_result"
        
        # Verify the request format
        call_args = mock_backend.send_request.call_args[0][0]
        assert call_args["method"] == "tools/call"
        assert call_args["params"]["name"] == "test_tool"
        assert call_args["params"]["arguments"] == {"param": "value"}
    
    @pytest.mark.asyncio
    async def test_forward_tool_call_error(self, forwarder):
        """Test error handling in tool call forwarding"""
        # Mock backend with error response
        mock_backend = AsyncMock()
        mock_backend.send_request = AsyncMock(
            return_value={"jsonrpc": "2.0", "error": {"message": "Tool error"}}
        )
        forwarder.backends["backend1"] = mock_backend
        
        with pytest.raises(Exception, match=r"Backend error: \{'message': 'Tool error'\}"):
            await forwarder.forward_tool_call("backend1", "test_tool", {})
    
    @pytest.mark.asyncio
    async def test_check_backend_health_unknown(self, forwarder):
        """Test health check for unknown backend"""
        result = await forwarder.check_backend_health("nonexistent")
        
        assert result["name"] == "nonexistent"
        assert result["status"] == "unknown"
        assert result["error"] == "Backend not found"
    
    @pytest.mark.asyncio
    async def test_check_backend_health_healthy(self, forwarder):
        """Test health check for healthy backend"""
        # Mock backend
        mock_backend = AsyncMock()
        mock_backend.config = BackendMCPConfig(
            name="backend1",
            command="echo",
            args=["test"],
            description="Test backend"
        )
        mock_backend.send_request = AsyncMock(
            return_value={
                "jsonrpc": "2.0",
                "result": {
                    "serverInfo": {
                        "name": "test_server",
                        "version": "1.0.0"
                    }
                }
            }
        )
        forwarder.backends["backend1"] = mock_backend
        
        result = await forwarder.check_backend_health("backend1")
        
        assert result["name"] == "backend1"
        assert result["status"] == "healthy"
        assert result["command"] == ["echo", "test"]
        assert result["info"]["name"] == "test_server"
    
    @pytest.mark.asyncio
    async def test_check_backend_health_unhealthy(self, forwarder):
        """Test health check for unhealthy backend"""
        # Mock backend that throws exception
        mock_backend = AsyncMock()
        mock_backend.send_request = AsyncMock(
            side_effect=Exception("Connection failed")
        )
        forwarder.backends["backend1"] = mock_backend
        
        result = await forwarder.check_backend_health("backend1")
        
        assert result["name"] == "backend1"
        assert result["status"] == "unhealthy"
        assert "Connection failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_close(self, forwarder):
        """Test closing all backends"""
        # Mock backends
        mock_backend1 = AsyncMock()
        mock_backend2 = AsyncMock()
        forwarder.backends = {
            "backend1": mock_backend1,
            "backend2": mock_backend2
        }
        
        await forwarder.close()
        
        assert mock_backend1.stop.called
        assert mock_backend2.stop.called
    
    def test_parse_backend_response_mcp_format(self, forwarder):
        """Test parsing MCP format response"""
        response = {
            "content": [
                {"type": "text", "text": "Line 1"},
                {"type": "text", "text": "Line 2"}
            ]
        }
        
        result = forwarder._parse_backend_response(response)
        assert result == "Line 1\nLine 2"
    
    def test_parse_backend_response_dict(self, forwarder):
        """Test parsing dictionary response"""
        response = {"key": "value", "number": 42}
        result = forwarder._parse_backend_response(response)
        
        # Should return JSON string
        assert '"key": "value"' in result
        assert '"number": 42' in result
    
    def test_parse_backend_response_string(self, forwarder):
        """Test parsing string response"""
        result = forwarder._parse_backend_response("simple string")
        assert result == "simple string"
    
    def test_parse_backend_response_other(self, forwarder):
        """Test parsing other types"""
        assert forwarder._parse_backend_response(123) == "123"
        assert forwarder._parse_backend_response([1, 2, 3]) == "[1, 2, 3]"


# Add this import at the top
import unittest.mock 