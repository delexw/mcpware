"""
Unit tests for backend module
"""
import json
import pytest
import asyncio
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from src.backend import substitute_env_vars, StdioBackend, BackendForwarder


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
        return {
            "command": ["echo", "test"],
            "timeout": 30,
            "env": {"TEST_ENV": "value"}
        }
    
    @pytest.fixture
    def backend(self, backend_config):
        """Fixture for StdioBackend instance"""
        return StdioBackend("test_backend", backend_config)
    
    def test_initialization(self, backend):
        """Test StdioBackend initialization"""
        assert backend.name == "test_backend"
        assert backend.config["command"] == ["echo", "test"]
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
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.stdout.readline = AsyncMock(return_value=b'')
        mock_process.stderr.readline = AsyncMock(return_value=b'')
        mock_subprocess.return_value = mock_process
        
        await backend.start()
        
        # Verify subprocess was created with correct parameters
        mock_subprocess.assert_called_once_with(
            "echo", "test",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=unittest.mock.ANY
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
        mock_process.stdin = Mock()  # Use regular Mock for stdin
        mock_process.stdin.write = Mock()  # Regular sync method
        mock_process.stdin.drain = AsyncMock()  # Async method
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.returncode = None  # Process is still running
        
        # Mock response
        response = {"jsonrpc": "2.0", "id": 1, "result": "test_result"}
        mock_process.stdout.readline = AsyncMock(
            side_effect=[
                json.dumps(response).encode() + b'\n',
                b''  # EOF
            ]
        )
        mock_process.stderr.readline = AsyncMock(return_value=b'')  # No stderr output
        mock_subprocess.return_value = mock_process
        
        await backend.start()
        
        # Send request
        request = {"method": "test_method", "params": {}}
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
    async def test_send_request_timeout(self, mock_subprocess, backend):
        """Test request timeout handling"""
        # Mock the subprocess
        mock_process = AsyncMock()
        mock_process.stdin = Mock()  # Use regular Mock for stdin
        mock_process.stdin.write = Mock()  # Regular sync method
        mock_process.stdin.drain = AsyncMock()  # Async method
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.returncode = None  # Process is still running
        mock_process.stdout.readline = AsyncMock(return_value=b'')  # No response
        mock_process.stderr.readline = AsyncMock(return_value=b'')  # No stderr output
        mock_subprocess.return_value = mock_process
        
        # Set short timeout
        backend.config["timeout"] = 0.1
        
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
        
        config = {
            "command": ["echo", "test"],
            "env": {
                "TEST_VAR_1": "${TEST_VAR_1}",
                "TEST_VAR_2": "${TEST_VAR_2}"
            },
            "timeout": 30
        }
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
        # Mock process
        backend.process = AsyncMock()
        backend.process.terminate = Mock()
        backend.process.kill = Mock()
        backend.process.wait = AsyncMock()
        backend.read_task = asyncio.create_task(asyncio.sleep(10))
        backend.stderr_task = asyncio.create_task(asyncio.sleep(10))
        
        await backend.stop()
        
        assert backend.process.terminate.called
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
            {
                "name": "backend1",
                "command": ["echo", "backend1"],
                "description": "Backend 1",
                "timeout": 30
            },
            {
                "name": "backend2",
                "command": ["echo", "backend2"],
                "description": "Backend 2",
                "timeout": 20
            }
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
        mock_backend.config = {"command": ["echo", "test"]}
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