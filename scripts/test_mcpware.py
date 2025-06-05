#!/usr/bin/env python3
"""Test script to verify mcpware MCP server functionality."""

import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional

# ANSI color codes for better output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'


@contextmanager
def mcpware_process(config_path: Path = Path("config.json")):
    """Context manager for managing the mcpware server process."""
    cmd = [sys.executable, "gateway_server.py", "--config", str(config_path)]
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    try:
        yield process
    finally:
        process.terminate()
        process.wait()


class MCPTester:
    """Test harness for mcpware MCP server."""
    
    def __init__(self, process: subprocess.Popen):
        self.process = process
        self.request_id = 0
        
    def send_message(self, message: Dict[str, Any]) -> None:
        """Send a JSON-RPC message to the MCP server."""
        msg_str = json.dumps(message)
        print(f"{Colors.BLUE}→ Sending:{Colors.RESET} {msg_str}")
        self.process.stdin.write(msg_str + '\n')
        self.process.stdin.flush()
    
    def read_response(self) -> Optional[Dict[str, Any]]:
        """Read a response from the MCP server."""
        if response := self.process.stdout.readline():
            data = json.loads(response)
            print(f"{Colors.BLUE}← Received:{Colors.RESET} {json.dumps(data, indent=2)}")
            return data
        return None
    
    def send_request(self, method: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Send a request and return the response."""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self.request_id
        }
        self.send_message(request)
        return self.read_response()
    
    def test_initialize(self) -> bool:
        """Test initialization."""
        print("\n1. Initializing connection...")
        response = self.send_request(
            "initialize",
            {
                "protocolVersion": "0.1.0",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        )
        
        if response and "result" in response:
            print(f"{Colors.GREEN}✅ Initialized successfully{Colors.RESET}")
            return True
        
        print(f"{Colors.RED}❌ Failed to initialize{Colors.RESET}")
        return False
    
    def test_list_tools(self) -> bool:
        """Test listing available tools."""
        print("\n2. Listing available tools...")
        response = self.send_request("tools/list")
        
        if not response or "result" not in response:
            print(f"{Colors.RED}❌ Failed to list tools{Colors.RESET}")
            return False
        
        tools = response["result"].get("tools", [])
        print(f"\n{Colors.GREEN}✅ Found {len(tools)} tools:{Colors.RESET}")
        for tool in tools:
            desc = tool.get('description', 'No description')
            print(f"   - {tool['name']}: {desc}")
        
        return True
    
    def test_discover_backends(self) -> bool:
        """Test backend discovery."""
        print("\n3. Testing discover_backend_tools...")
        response = self.send_request(
            "tools/call",
            {
                "name": "discover_backend_tools",
                "arguments": {}
            }
        )
        
        if response and "result" in response:
            print(f"{Colors.GREEN}✅ Backend discovery successful{Colors.RESET}")
            return True
        
        print(f"{Colors.RED}❌ Backend discovery failed{Colors.RESET}")
        return False
    
    def run_all_tests(self) -> bool:
        """Run all tests and return success status."""
        tests = [
            self.test_initialize,
            self.test_list_tools,
            self.test_discover_backends
        ]
        
        return all(test() for test in tests)


def main() -> int:
    """Main test function."""
    print("Starting mcpware server test...")
    
    try:
        with mcpware_process() as process:
            tester = MCPTester(process)
            success = tester.run_all_tests()
            
            if success:
                print(f"\n{Colors.GREEN}All tests passed!{Colors.RESET}")
                return 0
            else:
                print(f"\n{Colors.RED}Some tests failed!{Colors.RESET}")
                return 1
                
    except Exception as e:
        print(f"{Colors.RED}❌ Error: {e}{Colors.RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 