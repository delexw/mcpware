#!/usr/bin/env python3
"""
Check Docker socket configuration for the current platform.
Helps users determine the correct docker-compose configuration.
"""

import os
import platform
import subprocess
import sys


def check_docker_socket():
    """Check and report Docker socket configuration."""
    system = platform.system()
    print(f"Operating System: {system}")
    print(f"Platform: {platform.platform()}")
    
    # Check if Docker is installed
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Os}}"],
            capture_output=True,
            text=True,
            check=True
        )
        docker_os = result.stdout.strip()
        print(f"Docker Server OS: {docker_os}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Docker not found or not running")
        return
    
    # Determine socket path
    if system == "Windows":
        if docker_os == "linux":
            socket_path = "/var/run/docker.sock"
            print("\n✅ Using WSL2/Linux backend")
            print(f"Socket path: {socket_path}")
            print("No changes needed to docker-compose.yml")
        else:
            socket_path = "//./pipe/docker_engine"
            print("\n⚠️  Using Windows containers")
            print(f"Socket path: {socket_path}")
            print("\n📝 Create docker-compose.override.yml with:")
            print("""
services:
  mcpware:
    volumes:
      - ./config.json:/app/config.json:ro
      - //./pipe/docker_engine://./pipe/docker_engine
""")
    else:  # Linux, macOS, etc.
        socket_path = "/var/run/docker.sock"
        print(f"\n✅ Socket path: {socket_path}")
        print("No changes needed to docker-compose.yml")
        
        # Check if socket exists
        if os.path.exists(socket_path):
            print("✅ Docker socket found")
        else:
            print("❌ Docker socket not found at expected location")
    
    # Test Docker connectivity
    try:
        subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            check=True
        )
        print("✅ Docker connection successful")
    except subprocess.CalledProcessError:
        print("❌ Cannot connect to Docker daemon")
        if system != "Windows":
            print("   Try: sudo usermod -aG docker $USER")
            print("   Then log out and back in")


if __name__ == "__main__":
    check_docker_socket() 