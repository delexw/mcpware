"""
MCPProtocolHandler module for mcpware
Handles MCP protocol operations and message routing
"""
import logging
from typing import Dict, List, Any, Optional
import asyncio
import uuid

from .config import ConfigurationManager, BackendMCPConfig
from .backend_forwarder import BackendForwarder
from .security import SecurityValidator

logger = logging.getLogger(__name__)


class MCPProtocolHandler:
    """Handles MCP protocol operations"""
    
    def __init__(self, config_manager: ConfigurationManager, backend_forwarder: BackendForwarder):
        self.config_manager = config_manager
        self.backend_forwarder = backend_forwarder
        self._backend_capabilities = {}
        self._backend_tools = {}  # Cache tools by backend
        
        # Initialize security validator
        security_config = config_manager.config.get("security_policy", {})
        self.security_validator = SecurityValidator(security_config)
        
        # Track request sessions
        self._request_sessions: Dict[str, str] = {}  # request_id -> session_id
        
    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request"""
        # Initialize all backends and cache their capabilities
        for backend_name, backend_config in self.config_manager.backends.items():
            try:
                # Get backend capabilities
                init_request = {
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": params,
                    "id": f"init-{backend_name}"
                }
                
                backend_response = await self.backend_forwarder.forward_request(
                    backend_name, init_request
                )
                
                if "result" in backend_response:
                    capabilities = backend_response["result"].get("capabilities", {})
                    self._backend_capabilities[backend_name] = capabilities
                    
            except Exception as e:
                logger.error(f"Failed to initialize backend {backend_name}: {e}")
        
        # Return gateway capabilities with only our single tool
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}  # We support tools
            },
            "serverInfo": {
                "name": "mcpware",
                "version": "1.0.0",
                "vendor": "MCP Gateway"
            }
        }
    
    async def handle_initialized_notification(self) -> None:
        """Handle initialized notification by forwarding to all backends"""
        logger.info("Forwarding initialized notification to all backends")
        
        # Send initialized notification to each backend
        for backend_name in self.config_manager.backends.keys():
            try:
                # Send notification (no id, no response expected)
                notification = {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {}
                }
                
                # Forward without expecting response
                await self.backend_forwarder.send_notification(backend_name, notification)
                logger.info(f"Sent initialized notification to backend {backend_name}")
                
            except Exception as e:
                logger.error(f"Failed to send initialized notification to backend {backend_name}: {e}")
    
    async def handle_list_tools(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle tools/list request - return only the gateway's routing tool"""
        # Define the gateway's single routing tool
        use_tool = {
            "name": "use_tool",
            "description": "Route a tool call to a specific backend MCP server",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "backend_server": {
                        "type": "string",
                        "description": f"The backend server to use. Available servers: {', '.join(self.config_manager.backends.keys())}",
                        "enum": list(self.config_manager.backends.keys())
                    },
                    "server_tool": {
                        "type": "string",
                        "description": "The name of the tool to call on the backend server"
                    },
                    "tool_arguments": {
                        "type": "object",
                        "description": "Arguments to pass to the backend server's tool",
                        "additionalProperties": True
                    }
                },
                "required": ["backend_server", "server_tool"],
                "additionalProperties": False
            }
        }
        
        # Optionally add a discovery tool
        discover_tools = {
            "name": "discover_backend_tools",
            "description": "Discover available tools on backend MCP servers",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "backend_server": {
                        "type": "string",
                        "description": "The backend server to query for available tools (optional, omit to list all)",
                        "enum": list(self.config_manager.backends.keys())
                    }
                },
                "additionalProperties": False
            }
        }
        
        # Add security status tool
        security_status = {
            "name": "security_status",
            "description": "Get current session security status and access history",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        }
        
        return {"tools": [use_tool, discover_tools, security_status]}
    
    async def handle_tool_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request"""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        # Get or create session ID for this request context
        request_id = params.get("_request_id", str(uuid.uuid4()))
        session_id = self._get_or_create_session(request_id)
        
        if tool_name == "use_tool":
            return await self._handle_use_tool(arguments, session_id)
        elif tool_name == "discover_backend_tools":
            return await self._handle_discover_tools(arguments)
        elif tool_name == "security_status":
            return await self._handle_security_status(session_id)
        else:
            return self._create_error_response(f"Unknown tool: {tool_name}")
    
    def _get_or_create_session(self, request_id: str) -> str:
        """Get or create a session ID for the request"""
        if request_id not in self._request_sessions:
            # Create a new session ID
            session_id = str(uuid.uuid4())
            self._request_sessions[request_id] = session_id
            logger.info(f"Created new session {session_id} for request {request_id}")
        return self._request_sessions[request_id]
    
    async def _handle_use_tool(self, arguments: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Handle the use_tool routing call with security validation"""
        backend_server = arguments.get("backend_server")
        server_tool = arguments.get("server_tool")
        tool_arguments = arguments.get("tool_arguments", {})
        
        # Validate backend server
        if not backend_server:
            return self._create_error_response("Missing required parameter: backend_server")
        
        if backend_server not in self.config_manager.backends:
            available = ", ".join(self.config_manager.backends.keys())
            return self._create_error_response(
                f"Unknown backend server: {backend_server}. Available servers: {available}"
            )
        
        # Validate tool name
        if not server_tool:
            return self._create_error_response("Missing required parameter: server_tool")
        
        # SECURITY VALIDATION: Check if backend access is allowed
        is_allowed, error_msg = self.security_validator.validate_backend_access(
            session_id, backend_server, server_tool, tool_arguments
        )
        
        if not is_allowed:
            logger.warning(f"Security validation failed for {backend_server}/{server_tool}: {error_msg}")
            return self._create_error_response(f"Security validation failed: {error_msg}")
        
        try:
            # Forward the tool call to the backend
            tool_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": server_tool,
                    "arguments": tool_arguments
                },
                "id": f"tool-call-{backend_server}-{server_tool}"
            }
            
            response = await self.backend_forwarder.forward_request(
                backend_server, tool_request
            )
            
            if "result" in response:
                # SECURITY VALIDATION: Check response for sensitive data
                is_allowed, error_msg = self.security_validator.validate_response(
                    session_id, backend_server, response["result"]
                )
                
                if not is_allowed:
                    logger.warning(f"Response validation failed for {backend_server}: {error_msg}")
                    return self._create_error_response(f"Response blocked: {error_msg}")
                
                # Wrap the result with backend info
                result = response["result"]
                if isinstance(result, dict) and "content" in result:
                    # Add backend info to the response
                    for content_item in result.get("content", []):
                        if isinstance(content_item, dict) and content_item.get("type") == "text":
                            content_item["text"] = f"[{backend_server}] {content_item.get('text', '')}"
                return result
            elif "error" in response:
                return self._create_error_response(
                    f"Backend error from {backend_server}: {response['error'].get('message', 'Unknown error')}"
                )
            else:
                return self._create_error_response("Invalid response from backend")
                
        except Exception as e:
            logger.error(f"Error calling tool {server_tool} on {backend_server}: {e}")
            return self._create_error_response(f"Error: {str(e)}")
    
    async def _handle_security_status(self, session_id: str) -> Dict[str, Any]:
        """Handle security_status tool call"""
        summary = self.security_validator.get_session_summary(session_id)
        
        # Format the summary as readable text
        text = "🔒 Security Status Report\n"
        text += "=" * 40 + "\n\n"
        
        if "error" in summary:
            text += f"Error: {summary['error']}\n"
        else:
            text += f"Session ID: {summary['session_id']}\n"
            text += f"Started: {summary['started_at']}\n"
            text += f"Duration: {summary['duration_seconds']:.1f} seconds\n"
            text += f"Tainted: {'Yes' if summary['is_tainted'] else 'No'}\n"
            
            if summary['taint_source']:
                text += f"Taint Source: {summary['taint_source']}\n"
            
            text += f"\nAccessed Backends: {', '.join(summary['accessed_backends'])}\n"
            text += f"Total Accesses: {summary['total_accesses']}\n"
            text += f"Sensitive Data Accesses: {summary['sensitive_data_accesses']}\n"
            
            if summary['backend_sequence']:
                text += "\n📊 Recent Access History:\n"
                for access in summary['backend_sequence']:
                    text += f"  • {access['backend']} ({access['security_level']}) "
                    text += f"- {access['tool']}"
                    if access['has_sensitive_data']:
                        text += " ⚠️ [sensitive data]"
                    text += "\n"
        
        return {
            "content": [{
                "type": "text",
                "text": text
            }]
        }
    
    async def _handle_discover_tools(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the discover_backend_tools call"""
        backend_server = arguments.get("backend_server")
        
        # If specific backend requested
        if backend_server:
            if backend_server not in self.config_manager.backends:
                return self._create_error_response(f"Unknown backend server: {backend_server}")
            
            return await self._discover_single_backend_tools(backend_server)
        
        # Otherwise, discover all backends
        return await self._discover_all_backend_tools()
    
    async def _discover_single_backend_tools(self, backend_name: str) -> Dict[str, Any]:
        """Discover tools for a single backend"""
        try:
            # Simply try to get tools from the backend
            list_request = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": f"list-tools-{backend_name}"
            }
            
            response = await self.backend_forwarder.forward_request(
                backend_name, list_request
            )
            
            if "result" in response and "tools" in response["result"]:
                tools = response["result"]["tools"]
                
                # Cache tools
                self._backend_tools[backend_name] = tools
                
                # Format response
                backend_info = self.config_manager.backends[backend_name]
                tool_list = []
                for tool in tools:
                    tool_list.append(f"  - {tool['name']}: {tool.get('description', 'No description')}")
                
                text = f"Backend: {backend_name}\n"
                text += f"Description: {backend_info.description}\n"
                text += f"Available tools ({len(tools)}):\n"
                text += "\n".join(tool_list)
                
                return {
                    "content": [{
                        "type": "text",
                        "text": text
                    }]
                }
            else:
                return self._create_error_response(f"Failed to list tools from {backend_name}")
                
        except Exception as e:
            logger.error(f"Error discovering tools from {backend_name}: {e}")
            return self._create_error_response(f"Error: {str(e)}")
    
    async def _discover_all_backend_tools(self) -> Dict[str, Any]:
        """Discover tools for all backends"""
        discoveries = []
        
        for backend_name in self.config_manager.backends.keys():
            try:
                # Request tools from backend
                list_request = {
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": f"list-tools-{backend_name}"
                }
                
                response = await self.backend_forwarder.forward_request(
                    backend_name, list_request
                )
                
                if "result" in response and "tools" in response["result"]:
                    tools = response["result"]["tools"]
                    
                    # Cache tools
                    self._backend_tools[backend_name] = tools
                    
                    # Add to discoveries
                    backend_info = self.config_manager.backends[backend_name]
                    tool_list = []
                    for tool in tools[:5]:  # Show first 5 tools
                        tool_list.append(f"  - {tool['name']}: {tool.get('description', 'No description')}")
                    
                    discovery = f"\n📦 Backend: {backend_name}\n"
                    discovery += f"   Description: {backend_info.description}\n"
                    discovery += f"   Tools ({len(tools)} available):\n"
                    discovery += "\n".join(tool_list)
                    
                    if len(tools) > 5:
                        discovery += f"\n   ... and {len(tools) - 5} more tools"
                    
                    discoveries.append(discovery)
                    
            except Exception as e:
                logger.error(f"Error discovering tools from {backend_name}: {e}")
                discoveries.append(f"\n❌ Backend: {backend_name} - Error: {str(e)}")
        
        if not discoveries:
            text = "No backend servers with tools found."
        else:
            text = "Available Backend Servers and Tools:\n" + "\n".join(discoveries)
        
        return {
            "content": [{
                "type": "text",
                "text": text
            }]
        }
    
    async def handle_list_resources(self) -> Dict[str, List[Dict[str, Any]]]:
        """Handle resources/list request - aggregate resources from all backends"""
        all_resources = []
        
        # Get resources from each backend
        for backend_name in self.config_manager.backends.keys():
            if backend_name not in self._backend_capabilities:
                continue
                
            capabilities = self._backend_capabilities[backend_name]
            if "resources" not in capabilities:
                continue
                
            try:
                # Request resources from backend
                list_request = {
                    "jsonrpc": "2.0",
                    "method": "resources/list",
                    "id": f"list-resources-{backend_name}"
                }
                
                response = await self.backend_forwarder.forward_request(
                    backend_name, list_request
                )
                
                if "result" in response and "resources" in response["result"]:
                    backend_resources = response["result"]["resources"]
                    
                    # Prefix resource URIs with backend name
                    for resource in backend_resources:
                        prefixed_resource = {
                            "uri": f"{backend_name}:{resource['uri']}",
                            "name": f"[{backend_name}] {resource.get('name', '')}",
                            "description": resource.get("description", ""),
                            "mimeType": resource.get("mimeType", "text/plain")
                        }
                        all_resources.append(prefixed_resource)
                        
            except Exception as e:
                logger.error(f"Failed to list resources from backend {backend_name}: {e}")
        
        return {"resources": all_resources}
    
    async def handle_read_resource(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/read request - forward to appropriate backend"""
        uri = params.get("uri", "")
        
        # Extract backend name from prefixed URI
        if ":" not in uri:
            return self._create_error_response(f"Invalid resource URI format: {uri}")
            
        backend_name, original_uri = uri.split(":", 1)
        
        if backend_name not in self.config_manager.backends:
            return self._create_error_response(f"Unknown backend: {backend_name}")
        
        try:
            # Forward the resource read to the backend
            read_request = {
                "jsonrpc": "2.0",
                "method": "resources/read",
                "params": {
                    "uri": original_uri
                },
                "id": f"read-resource-{backend_name}"
            }
            
            response = await self.backend_forwarder.forward_request(
                backend_name, read_request
            )
            
            if "result" in response:
                return response["result"]
            elif "error" in response:
                return self._create_error_response(
                    f"Backend error: {response['error'].get('message', 'Unknown error')}"
                )
            else:
                return self._create_error_response("Invalid response from backend")
                
        except Exception as e:
            logger.error(f"Error reading resource {uri}: {e}")
            return self._create_error_response(str(e))
    
    async def handle_list_prompts(self) -> Dict[str, List[Dict[str, Any]]]:
        """Handle prompts/list request - aggregate prompts from all backends"""
        all_prompts = []
        
        # Get prompts from each backend
        for backend_name in self.config_manager.backends.keys():
            if backend_name not in self._backend_capabilities:
                continue
                
            capabilities = self._backend_capabilities[backend_name]
            if "prompts" not in capabilities:
                continue
                
            try:
                # Request prompts from backend
                list_request = {
                    "jsonrpc": "2.0",
                    "method": "prompts/list",
                    "id": f"list-prompts-{backend_name}"
                }
                
                response = await self.backend_forwarder.forward_request(
                    backend_name, list_request
                )
                
                if "result" in response and "prompts" in response["result"]:
                    backend_prompts = response["result"]["prompts"]
                    
                    # Prefix prompt names with backend name
                    for prompt in backend_prompts:
                        prefixed_prompt = {
                            "name": f"{backend_name}_{prompt['name']}",
                            "description": f"[{backend_name}] {prompt.get('description', '')}",
                            "arguments": prompt.get("arguments", [])
                        }
                        all_prompts.append(prefixed_prompt)
                        
            except Exception as e:
                logger.error(f"Failed to list prompts from backend {backend_name}: {e}")
        
        return {"prompts": all_prompts}
    
    async def handle_get_prompt(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle prompts/get request - forward to appropriate backend"""
        prompt_name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        # Extract backend name from prefixed prompt name
        parts = prompt_name.split("_", 1)
        if len(parts) < 2:
            return self._create_error_response(f"Invalid prompt name format: {prompt_name}")
            
        backend_name, original_prompt_name = parts
        
        if backend_name not in self.config_manager.backends:
            return self._create_error_response(f"Unknown backend: {backend_name}")
        
        try:
            # Forward the prompt get to the backend
            get_request = {
                "jsonrpc": "2.0",
                "method": "prompts/get",
                "params": {
                    "name": original_prompt_name,
                    "arguments": arguments
                },
                "id": f"get-prompt-{backend_name}"
            }
            
            response = await self.backend_forwarder.forward_request(
                backend_name, get_request
            )
            
            if "result" in response:
                return response["result"]
            elif "error" in response:
                return self._create_error_response(
                    f"Backend error: {response['error'].get('message', 'Unknown error')}"
                )
            else:
                return self._create_error_response("Invalid response from backend")
                
        except Exception as e:
            logger.error(f"Error getting prompt {prompt_name}: {e}")
            return self._create_error_response(str(e))
    
    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create an error response"""
        return {
            "content": [{
                "type": "text",
                "text": f"Error: {error_message}"
            }],
            "isError": True
        } 