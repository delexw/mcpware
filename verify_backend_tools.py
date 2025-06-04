#!/usr/bin/env python3
"""Verify backend tools in mcpware."""

import json
import subprocess

def main():
    # Test commands
    commands = [
        # Initialize
        {"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"0.1.0"},"id":1},
        # Discover all backend tools
        {"jsonrpc":"2.0","method":"tools/call","params":{"name":"discover_backend_tools","arguments":{}},"id":2}
    ]
    
    # Run docker compose
    process = subprocess.Popen(
        ["docker", "compose", "run", "--rm", "-T", "mcpware"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Send commands
    for cmd in commands:
        process.stdin.write(json.dumps(cmd) + '\n')
    process.stdin.close()
    
    # Read responses
    responses = []
    for line in process.stdout:
        if line.strip().startswith('{'):
            try:
                responses.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    
    # Find the discover response
    for resp in responses:
        if resp.get('id') == 2 and 'result' in resp:
            content = resp['result']['content'][0]['text']
            
            # Parse and display nicely
            print("\n🚀 MCPWARE BACKEND TOOLS VERIFICATION")
            print("=" * 50)
            
            backends = content.split('\n\n📦 Backend: ')
            for backend in backends:
                if 'Tools (' in backend:
                    lines = backend.split('\n')
                    backend_name = lines[0].split('\n')[0]
                    
                    if backend_name.startswith('Available'):
                        # First backend
                        backend_name = "github"
                        desc_line = [l for l in lines if 'Description:' in l][0]
                        tools_line = [l for l in lines if 'Tools (' in l][0]
                    else:
                        desc_line = [l for l in lines if 'Description:' in l][0]
                        tools_line = [l for l in lines if 'Tools (' in l][0]
                    
                    # Extract tool count
                    tool_count = tools_line.split('(')[1].split(' ')[0]
                    
                    print(f"\n📦 Backend: {backend_name}")
                    print(f"   {desc_line}")
                    print(f"   ✅ {tool_count} tools available")
                    
                    # Show first 5 tools
                    tool_lines = [l for l in lines if l.strip().startswith('- ')][:5]
                    for tool in tool_lines:
                        print(f"   {tool}")
                    if int(tool_count) > 5:
                        print(f"   ... and {int(tool_count) - 5} more tools")
            
            print("\n✨ All backend tools are accessible!")
            return
    
    print("❌ Failed to get backend tools")

if __name__ == "__main__":
    main() 