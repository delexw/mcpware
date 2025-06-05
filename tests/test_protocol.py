"""
Unit tests for protocol module
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from src.protocol import MCPProtocolHandler, JSONRPCHandler
from src.config import ConfigurationManager, BackendMCPConfig
from src.backend import BackendForwarder


class TestMCPProtocolHandler:
    """Test cases for MCPProtocolHandler class"""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Fixture for mock ConfigurationManager"""
        config_manager = Mock(spec=ConfigurationManager)
        config_manager.backends = {
            "backend1": Mock(
                name="backend1",
                command=["echo", "test"],
                description="Backend 1",
                timeout=30,
                env={}
            ),
            "backend2": Mock(
                name="backend2",
                command=["echo", "test2"],
                description="Backend 2",
                timeout=30,
                env={}
            )
        }
        # Add required config attribute with security_policy
        config_manager.config = {
            "security_policy": {
                "backend_security_levels": {
                    "backend1": "public",
                    "backend2": "internal"
                }
            }
        }
        return config_manager
    
    @pytest.fixture
    def mock_backend_forwarder(self):
        """Fixture for mock BackendForwarder"""
        return AsyncMock(spec=BackendForwarder)
    
    @pytest.fixture
    def protocol_handler(self, mock_config_manager, mock_backend_forwarder):
        """Fixture for MCPProtocolHandler instance"""
        return MCPProtocolHandler(mock_config_manager, mock_backend_forwarder)
    
    @pytest.mark.asyncio
    async def test_handle_initialize(self, protocol_handler, mock_backend_forwarder):
        """Test handling initialize request"""
        # Mock backend responses
        mock_backend_forwarder.forward_request.side_effect = [
            {
                "jsonrpc": "2.0",
                "result": {
                    "capabilities": {"tools": {}, "resources": {}},
                    "serverInfo": {"name": "backend1"}
                }
            },
            {
                "jsonrpc": "2.0",
                "result": {
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "backend2"}
                }
            }
        ]
        
        params = {"protocolVersion": "2024-11-05", "capabilities": {}}
        result = await protocol_handler.handle_initialize(params)
        
        assert result["protocolVersion"] == "2024-11-05"
        assert "tools" in result["capabilities"]
        assert result["serverInfo"]["name"] == "gateway-mcp-server"
        
        # Verify backend capabilities were cached
        assert "backend1" in protocol_handler._backend_capabilities
        assert "backend2" in protocol_handler._backend_capabilities
        assert "resources" in protocol_handler._backend_capabilities["backend1"]
    
    @pytest.mark.asyncio
    async def test_handle_initialize_backend_failure(self, protocol_handler, mock_backend_forwarder):
        """Test handling initialize when a backend fails"""
        # Mock one backend failing
        mock_backend_forwarder.forward_request.side_effect = [
            Exception("Backend 1 failed"),
            {
                "jsonrpc": "2.0",
                "result": {
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "backend2"}
                }
            }
        ]
        
        params = {"protocolVersion": "2024-11-05", "capabilities": {}}
        result = await protocol_handler.handle_initialize(params)
        
        # Should still return success
        assert result["protocolVersion"] == "2024-11-05"
        assert "backend2" in protocol_handler._backend_capabilities
        assert "backend1" not in protocol_handler._backend_capabilities
    
    @pytest.mark.asyncio
    async def test_handle_list_tools(self, protocol_handler):
        """Test handling tools/list request"""
        result = await protocol_handler.handle_list_tools()
        
        assert "tools" in result
        tools = result["tools"]
        assert len(tools) == 3  # use_tool, discover_backend_tools, security_status
        
        # Check use_tool
        use_tool = next(t for t in tools if t["name"] == "use_tool")
        assert "backend_server" in use_tool["inputSchema"]["properties"]
        assert "server_tool" in use_tool["inputSchema"]["properties"]
        assert "tool_arguments" in use_tool["inputSchema"]["properties"]
        
        # Check discover_backend_tools
        discover_tool = next(t for t in tools if t["name"] == "discover_backend_tools")
        assert "backend_server" in discover_tool["inputSchema"]["properties"]
        
        # Check security_status
        security_tool = next(t for t in tools if t["name"] == "security_status")
        assert security_tool["description"] == "Get current session security status and access history"
    
    @pytest.mark.asyncio
    async def test_handle_tool_call_use_tool(self, protocol_handler, mock_backend_forwarder):
        """Test handling tools/call for use_tool"""
        # Mock backend response
        mock_backend_forwarder.forward_request.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "content": [{"type": "text", "text": "Tool executed"}]
            }
        }
        
        params = {
            "name": "use_tool",
            "arguments": {
                "backend_server": "backend1",
                "server_tool": "test_tool",
                "tool_arguments": {"param": "value"}
            }
        }
        
        result = await protocol_handler.handle_tool_call(params)
        
        assert "content" in result
        assert result["content"][0]["text"] == "[backend1] Tool executed"
    
    @pytest.mark.asyncio
    async def test_handle_tool_call_missing_backend(self, protocol_handler):
        """Test handling tool call with missing backend"""
        params = {
            "name": "use_tool",
            "arguments": {
                "backend_server": "nonexistent",
                "server_tool": "test_tool"
            }
        }
        
        result = await protocol_handler.handle_tool_call(params)
        
        assert result["isError"] is True
        assert "Unknown backend server: nonexistent" in result["content"][0]["text"]
    
    @pytest.mark.asyncio
    async def test_handle_tool_call_backend_error(self, protocol_handler, mock_backend_forwarder):
        """Test handling tool call when backend returns error"""
        mock_backend_forwarder.forward_request.return_value = {
            "jsonrpc": "2.0",
            "error": {"message": "Tool not found"}
        }
        
        params = {
            "name": "use_tool",
            "arguments": {
                "backend_server": "backend1",
                "server_tool": "nonexistent_tool"
            }
        }
        
        result = await protocol_handler.handle_tool_call(params)
        
        assert result["isError"] is True
        assert "Tool not found" in result["content"][0]["text"]
    
    @pytest.mark.asyncio
    async def test_handle_discover_tools_single(self, protocol_handler, mock_backend_forwarder):
        """Test discovering tools for a single backend"""
        # Set up backend capabilities
        protocol_handler._backend_capabilities = {"backend1": {"tools": {}}}
        
        # Mock backend response
        mock_backend_forwarder.forward_request.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "tools": [
                    {"name": "tool1", "description": "Tool 1"},
                    {"name": "tool2", "description": "Tool 2"}
                ]
            }
        }
        
        params = {
            "name": "discover_backend_tools",
            "arguments": {"backend_server": "backend1"}
        }
        
        result = await protocol_handler.handle_tool_call(params)
        
        assert "Backend: backend1" in result["content"][0]["text"]
        assert "tool1: Tool 1" in result["content"][0]["text"]
        assert "tool2: Tool 2" in result["content"][0]["text"]
    
    @pytest.mark.asyncio
    async def test_handle_discover_tools_all(self, protocol_handler, mock_backend_forwarder):
        """Test discovering tools for all backends"""
        # Set up backend capabilities
        protocol_handler._backend_capabilities = {
            "backend1": {"tools": {}},
            "backend2": {"tools": {}}
        }
        
        # Mock backend responses
        mock_backend_forwarder.forward_request.side_effect = [
            {
                "jsonrpc": "2.0",
                "result": {
                    "tools": [{"name": "tool1", "description": "Tool 1"}]
                }
            },
            {
                "jsonrpc": "2.0",
                "result": {
                    "tools": [{"name": "tool2", "description": "Tool 2"}]
                }
            }
        ]
        
        params = {
            "name": "discover_backend_tools",
            "arguments": {}
        }
        
        result = await protocol_handler.handle_tool_call(params)
        
        text = result["content"][0]["text"]
        assert "Backend: backend1" in text
        assert "Backend: backend2" in text
    
    @pytest.mark.asyncio
    async def test_handle_list_resources(self, protocol_handler, mock_backend_forwarder):
        """Test handling resources/list request"""
        # Set up backend capabilities
        protocol_handler._backend_capabilities = {
            "backend1": {"resources": {}},
            "backend2": {"resources": {}}
        }
        
        # Mock backend responses
        mock_backend_forwarder.forward_request.side_effect = [
            {
                "jsonrpc": "2.0",
                "result": {
                    "resources": [
                        {
                            "uri": "file://test.txt",
                            "name": "Test File",
                            "description": "A test file",
                            "mimeType": "text/plain"
                        }
                    ]
                }
            },
            {
                "jsonrpc": "2.0",
                "result": {
                    "resources": [
                        {
                            "uri": "file://test2.txt",
                            "name": "Test File 2",
                            "description": "Another test file"
                        }
                    ]
                }
            }
        ]
        
        result = await protocol_handler.handle_list_resources()
        
        assert "resources" in result
        resources = result["resources"]
        assert len(resources) == 2
        
        # Check that URIs are prefixed
        assert resources[0]["uri"] == "backend1:file://test.txt"
        assert resources[0]["name"] == "[backend1] Test File"
        assert resources[1]["uri"] == "backend2:file://test2.txt"
        assert resources[1]["name"] == "[backend2] Test File 2"
    
    @pytest.mark.asyncio
    async def test_handle_read_resource(self, protocol_handler, mock_backend_forwarder):
        """Test handling resources/read request"""
        # Mock backend response
        mock_backend_forwarder.forward_request.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "content": "File content here"
            }
        }
        
        params = {"uri": "backend1:file://test.txt"}
        result = await protocol_handler.handle_read_resource(params)
        
        assert result["content"] == "File content here"
        
        # Verify the backend was called with the original URI
        mock_backend_forwarder.forward_request.assert_called_once()
        call_args = mock_backend_forwarder.forward_request.call_args[0]
        assert call_args[0] == "backend1"
        assert call_args[1]["params"]["uri"] == "file://test.txt"
    
    @pytest.mark.asyncio
    async def test_handle_read_resource_invalid_uri(self, protocol_handler):
        """Test handling resources/read with invalid URI"""
        params = {"uri": "invalid_uri_format"}
        result = await protocol_handler.handle_read_resource(params)
        
        assert result["isError"] is True
        assert "Invalid resource URI format" in result["content"][0]["text"]
    
    @pytest.mark.asyncio
    async def test_handle_list_prompts(self, protocol_handler, mock_backend_forwarder):
        """Test handling prompts/list request"""
        # Set up backend capabilities
        protocol_handler._backend_capabilities = {
            "backend1": {"prompts": {}},
            "backend2": {"prompts": {}}
        }
        
        # Mock backend responses
        mock_backend_forwarder.forward_request.side_effect = [
            {
                "jsonrpc": "2.0",
                "result": {
                    "prompts": [
                        {
                            "name": "prompt1",
                            "description": "Prompt 1",
                            "arguments": [{"name": "arg1", "type": "string"}]
                        }
                    ]
                }
            },
            {
                "jsonrpc": "2.0",
                "result": {
                    "prompts": [
                        {
                            "name": "prompt2",
                            "description": "Prompt 2",
                            "arguments": []
                        }
                    ]
                }
            }
        ]
        
        result = await protocol_handler.handle_list_prompts()
        
        assert "prompts" in result
        prompts = result["prompts"]
        assert len(prompts) == 2
        
        # Check that prompt names are prefixed
        assert prompts[0]["name"] == "backend1_prompt1"
        assert prompts[0]["description"] == "[backend1] Prompt 1"
        assert prompts[1]["name"] == "backend2_prompt2"
        assert prompts[1]["description"] == "[backend2] Prompt 2"
    
    @pytest.mark.asyncio
    async def test_handle_get_prompt(self, protocol_handler, mock_backend_forwarder):
        """Test handling prompts/get request"""
        # Mock backend response
        mock_backend_forwarder.forward_request.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "messages": [{"role": "user", "content": "Test prompt"}]
            }
        }
        
        params = {
            "name": "backend1_prompt1",
            "arguments": {"arg1": "value1"}
        }
        result = await protocol_handler.handle_get_prompt(params)
        
        assert result["messages"][0]["content"] == "Test prompt"
        
        # Verify the backend was called with the original prompt name
        mock_backend_forwarder.forward_request.assert_called_once()
        call_args = mock_backend_forwarder.forward_request.call_args[0]
        assert call_args[0] == "backend1"
        assert call_args[1]["params"]["name"] == "prompt1"
    
    @pytest.mark.asyncio
    async def test_handle_get_prompt_invalid_format(self, protocol_handler):
        """Test handling prompts/get with invalid prompt name format"""
        params = {"name": "invalid_prompt_name"}
        result = await protocol_handler.handle_get_prompt(params)
        
        assert result["isError"] is True
        assert "Unknown backend: invalid" in result["content"][0]["text"]
    
    def test_create_error_response(self, protocol_handler):
        """Test creating error response"""
        result = protocol_handler._create_error_response("Test error message")
        
        assert result["isError"] is True
        assert result["content"][0]["type"] == "text"
        assert result["content"][0]["text"] == "Error: Test error message"


class TestJSONRPCHandler:
    """Test cases for JSONRPCHandler class"""
    
    @pytest.fixture
    def mock_protocol_handler(self):
        """Fixture for mock MCPProtocolHandler"""
        return AsyncMock(spec=MCPProtocolHandler)
    
    @pytest.fixture
    def jsonrpc_handler(self, mock_protocol_handler):
        """Fixture for JSONRPCHandler instance"""
        return JSONRPCHandler(mock_protocol_handler)
    
    @pytest.mark.asyncio
    async def test_handle_request_initialize(self, jsonrpc_handler, mock_protocol_handler):
        """Test handling initialize request"""
        mock_protocol_handler.handle_initialize.return_value = {
            "protocolVersion": "2024-11-05",
            "capabilities": {}
        }
        
        request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
            "id": 1
        }
        
        response = await jsonrpc_handler.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["protocolVersion"] == "2024-11-05"
    
    @pytest.mark.asyncio
    async def test_handle_request_tools_list(self, jsonrpc_handler, mock_protocol_handler):
        """Test handling tools/list request"""
        mock_protocol_handler.handle_list_tools.return_value = {
            "tools": [{"name": "test_tool"}]
        }
        
        request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 2
        }
        
        response = await jsonrpc_handler.handle_request(request)
        
        assert response["id"] == 2
        assert "tools" in response["result"]
    
    @pytest.mark.asyncio
    async def test_handle_request_tools_call(self, jsonrpc_handler, mock_protocol_handler):
        """Test handling tools/call request"""
        mock_protocol_handler.handle_tool_call.return_value = {
            "content": [{"type": "text", "text": "Result"}]
        }
        
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "test_tool", "arguments": {}},
            "id": 3
        }
        
        response = await jsonrpc_handler.handle_request(request)
        
        assert response["id"] == 3
        assert "content" in response["result"]
    
    @pytest.mark.asyncio
    async def test_handle_request_resources_list(self, jsonrpc_handler, mock_protocol_handler):
        """Test handling resources/list request"""
        mock_protocol_handler.handle_list_resources.return_value = {
            "resources": []
        }
        
        request = {
            "jsonrpc": "2.0",
            "method": "resources/list",
            "id": 4
        }
        
        response = await jsonrpc_handler.handle_request(request)
        
        assert response["id"] == 4
        assert "resources" in response["result"]
    
    @pytest.mark.asyncio
    async def test_handle_request_unsupported_method(self, jsonrpc_handler):
        """Test handling unsupported method"""
        request = {
            "jsonrpc": "2.0",
            "method": "unsupported/method",
            "id": 5
        }
        
        response = await jsonrpc_handler.handle_request(request)
        
        assert response["id"] == 5
        assert "error" in response
        assert response["error"]["code"] == -32601
        assert "Method not found" in response["error"]["message"]
    
    @pytest.mark.asyncio
    async def test_handle_request_exception(self, jsonrpc_handler, mock_protocol_handler):
        """Test handling request that throws exception"""
        mock_protocol_handler.handle_initialize.side_effect = Exception("Test exception")
        
        request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {},
            "id": 6
        }
        
        response = await jsonrpc_handler.handle_request(request)
        
        assert response["id"] == 6
        assert "error" in response
        assert response["error"]["code"] == -32603
        assert response["error"]["message"] == "Internal error"
        assert response["error"]["data"] == "Test exception"
    
    @pytest.mark.asyncio
    async def test_handle_notification(self, jsonrpc_handler, mock_protocol_handler):
        """Test handling notification (no id)"""
        request = {
            "jsonrpc": "2.0",
            "method": "notifications/cancelled",
            "params": {"requestId": "some-id"}
            # No "id" field - this is a notification
        }
        
        response = await jsonrpc_handler.handle_request(request)
        
        # Notifications should return None (no response)
        assert response is None
        
        # The protocol handler should not be called for notifications
        mock_protocol_handler.handle_initialize.assert_not_called()
    
    def test_create_success_response(self, jsonrpc_handler):
        """Test creating success response"""
        response = jsonrpc_handler._create_success_response(123, {"test": "result"})
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 123
        assert response["result"] == {"test": "result"}
    
    def test_create_error_response(self, jsonrpc_handler):
        """Test creating error response"""
        response = jsonrpc_handler._create_error_response(
            456, -32601, "Method not found", "Additional data"
        )
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 456
        assert response["error"]["code"] == -32601
        assert response["error"]["message"] == "Method not found"
        assert response["error"]["data"] == "Additional data" 