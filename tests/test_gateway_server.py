"""
Integration tests for gateway_server module
"""
import json
import pytest
import asyncio
import sys
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from io import StringIO

# We need to test the main function and the overall integration


class TestGatewayServerIntegration:
    """Integration tests for the gateway server"""
    
    @pytest.mark.asyncio
    @patch('sys.stdin')
    @patch('sys.stdout', new_callable=StringIO)
    @patch('src.backend.BackendForwarder')
    @patch('src.config.ConfigurationManager')
    async def test_main_initialize_request(self, mock_config_manager, mock_backend_forwarder, mock_stdout, mock_stdin):
        """Test handling initialize request through main"""
        # Import here to avoid issues with patching
        from gateway_server import main
        
        # Mock configuration
        mock_config = Mock()
        mock_config.backends = {
            "test_backend": Mock(
                name="test_backend",
                command=["echo", "test"],
                description="Test backend",
                timeout=30,
                env={}
            )
        }
        mock_config_manager.return_value.load.return_value = mock_config.backends
        mock_config_manager.return_value.backends = mock_config.backends
        
        # Mock backend forwarder
        mock_forwarder_instance = AsyncMock()
        mock_forwarder_instance.initialize = AsyncMock()
        mock_forwarder_instance.close = AsyncMock()
        mock_backend_forwarder.return_value = mock_forwarder_instance
        
        # Mock stdin with initialize request
        request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
            "id": 1
        }
        mock_stdin.readline.side_effect = [
            json.dumps(request) + "\n",
            ""  # EOF
        ]
        
        # Run main with test arguments
        with patch('sys.argv', ['gateway_server.py', '--config', 'tests/test_config.json']):
            await main()
        
        # Check output
        output = mock_stdout.getvalue()
        response_lines = output.strip().split('\n')
        assert len(response_lines) > 0
        
        response = json.loads(response_lines[0])
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["protocolVersion"] == "2024-11-05"
    
    @pytest.mark.asyncio
    @patch('sys.stdin')
    @patch('sys.stdout', new_callable=StringIO)
    async def test_main_invalid_json(self, mock_stdout, mock_stdin):
        """Test handling invalid JSON input"""
        from gateway_server import main
        
        # Mock stdin with invalid JSON that looks like JSON-RPC
        mock_stdin.readline.side_effect = [
            '{"jsonrpc": "2.0", invalid json }\n',
            ""  # EOF
        ]
        
        # Run main
        with patch('sys.argv', ['gateway_server.py']):
            await main()
        
        # Check error output
        output = mock_stdout.getvalue()
        response = json.loads(output.strip())
        assert response["error"]["code"] == -32700
        assert "Parse error" in response["error"]["message"]
    
    @pytest.mark.asyncio
    @patch('asyncio.get_event_loop')
    async def test_main_keyboard_interrupt(self, mock_loop):
        """Test handling keyboard interrupt"""
        from gateway_server import main
        
        # Mock the event loop to raise KeyboardInterrupt
        mock_loop.return_value.run_in_executor.side_effect = KeyboardInterrupt()
        
        # Run main - should handle interrupt gracefully
        with patch('sys.argv', ['gateway_server.py']):
            await main()  # Should not raise exception
    
    def test_main_entry_point(self):
        """Test the script entry point"""
        # Test that the script can be imported without side effects
        import gateway_server
        assert hasattr(gateway_server, 'main')
        assert callable(gateway_server.main)


class TestEndToEnd:
    """End-to-end tests with mock backends"""
    
    @pytest.fixture
    def mock_subprocess(self):
        """Create a mock subprocess that simulates a backend"""
        class MockProcess:
            def __init__(self):
                self.stdin = Mock()
                self.stdout = Mock()
                self.stderr = Mock()
                self.returncode = None
                self._responses = []
                self._response_index = 0
                
            def add_response(self, response):
                self._responses.append(json.dumps(response).encode() + b'\n')
                
            async def wait(self):
                self.returncode = 0
                
            def terminate(self):
                pass
                
            def kill(self):
                pass
                
        process = MockProcess()
        
        # Make stdout.readline return responses
        async def readline():
            if process._response_index < len(process._responses):
                response = process._responses[process._response_index]
                process._response_index += 1
                return response
            return b''
            
        process.stdout.readline = readline
        process.stdin.write = Mock(return_value=10)  # Mock write to return bytes written
        process.stdin.drain = AsyncMock()
        
        return process
    
    @pytest.mark.asyncio
    async def test_tool_call_flow(self):
        """Test complete tool call flow through the system"""
        from src.config import ConfigurationManager, BackendMCPConfig
        from src.backend_forwarder import BackendForwarder
        from src.mcp_protocol_handler import MCPProtocolHandler
        from src.jsonrpc_handler import JSONRPCHandler
        
        # Create real components
        config_manager = ConfigurationManager()
        config_manager.backends = {
            "test_backend": BackendMCPConfig(
                name="test_backend",
                command=["echo", "test"],
                description="Test backend"
            )
        }
        
        # Create a mock backend forwarder
        backend_forwarder = AsyncMock(spec=BackendForwarder)
        
        # Mock the forward_request method to return appropriate responses
        async def mock_forward_request(backend_name, request):
            if request.get("method") == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "test_backend", "version": "1.0"}
                    }
                }
            elif request.get("method") == "tools/call":
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "content": [{"type": "text", "text": "Tool executed successfully"}]
                    }
                }
            return {"jsonrpc": "2.0", "id": request.get("id"), "error": {"message": "Unknown method"}}
        
        backend_forwarder.forward_request = AsyncMock(side_effect=mock_forward_request)
        backend_forwarder.initialize = AsyncMock()
        backend_forwarder.close = AsyncMock()
        
        protocol_handler = MCPProtocolHandler(config_manager, backend_forwarder)
        jsonrpc_handler = JSONRPCHandler(protocol_handler)
        
        # Initialize
        init_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
            "id": 1
        }
        init_response = await jsonrpc_handler.handle_request(init_request)
        assert init_response["result"]["protocolVersion"] == "2024-11-05"
        
        # Call tool
        tool_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "use_tool",
                "arguments": {
                    "backend_server": "test_backend",
                    "server_tool": "my_tool",
                    "tool_arguments": {"param": "value"}
                }
            },
            "id": 2
        }
        tool_response = await jsonrpc_handler.handle_request(tool_request)
        
        assert tool_response["id"] == 2
        assert "result" in tool_response
        assert tool_response["result"]["content"][0]["text"] == "[test_backend] Tool executed successfully"
        
        # Clean up
        await backend_forwarder.close()


@pytest.fixture
def cleanup_env():
    """Clean up environment variables after tests"""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


import os  # Add this import at the end 