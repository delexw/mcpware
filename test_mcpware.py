#!/usr/bin/env python3
"""Test script to verify mcpware MCP server functionality."""

import json
import subprocess
import sys

def send_message(process, message):
    """Send a JSON-RPC message to the MCP server."""
    msg_str = json.dumps(message)
    print(f"→ Sending: {msg_str}")
    process.stdin.write(msg_str + '\n')
    process.stdin.flush()

def read_response(process):
    """Read a response from the MCP server."""
    response = process.stdout.readline()
    if response:
        data = json.loads(response)
        print(f"← Received: {json.dumps(data, indent=2)}")
        return data
    return None

def test_mcpware():
    """Test the mcpware server."""
    print("Starting mcpware server test...\n")
    
    # Start the server
    cmd = ["python", "gateway_server.py", "--config", "config.json"]
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    try:
        # 1. Send initialize request
        print("1. Initializing connection...")
        init_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "0.1.0",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            },
            "id": 1
        }
        send_message(process, init_request)
        init_response = read_response(process)
        
        if not init_response or "result" not in init_response:
            print("❌ Failed to initialize")
            return False
            
        print("✅ Initialized successfully\n")
        
        # 2. List available tools
        print("2. Listing available tools...")
        tools_request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 2
        }
        send_message(process, tools_request)
        tools_response = read_response(process)
        
        if not tools_response or "result" not in tools_response:
            print("❌ Failed to list tools")
            return False
            
        tools = tools_response["result"].get("tools", [])
        print(f"\n✅ Found {len(tools)} tools:")
        for tool in tools:
            print(f"   - {tool['name']}: {tool.get('description', 'No description')}")
        
        # 3. Test discover_backend_tools
        print("\n3. Testing discover_backend_tools...")
        discover_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "discover_backend_tools",
                "arguments": {}
            },
            "id": 3
        }
        send_message(process, discover_request)
        discover_response = read_response(process)
        
        if discover_response and "result" in discover_response:
            print("✅ Backend discovery successful")
        else:
            print("❌ Backend discovery failed")
            
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        process.terminate()
        process.wait()

if __name__ == "__main__":
    success = test_mcpware()
    sys.exit(0 if success else 1) 