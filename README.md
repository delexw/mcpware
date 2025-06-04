# Gateway MCP Server

<div align="center">
  <img src="mcpware-avatar-tech.svg" width="128" height="128" alt="Gateway MCP Server Logo">
</div>

<div align="center">

[![Tests](https://github.com/delexw/mcpware/actions/workflows/tests.yml/badge.svg)](https://github.com/delexw/mcpware/actions/workflows/tests.yml)
[![Coverage](https://img.shields.io/badge/coverage-87%25-brightgreen.svg)](https://github.com/delexw/mcpware)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

A Model Context Protocol (MCP) gateway server that routes tool calls to multiple stdio-based MCP backend servers.

## Overview

mcpware acts as a gateway/router for MCP, allowing AI agents to access multiple MCP servers through a single connection. It provides:

- **Single entry point**: Connect to multiple MCP servers through one gateway
- **Tool routing**: Routes tool calls to appropriate backend servers
- **Backend discovery**: Discover available backends and their tools
- **Process management**: Automatically launches and manages backend MCP server processes

## Quick Start

```bash
# Clone the repository
git clone https://github.com/delexw/mcpware.git
cd mcpware

# Set up environment (optional if using env in Claude config)
echo "GITHUB_PERSONAL_ACCESS_TOKEN=your_token_here" > .env

# Build the Docker image
docker compose build

# Configure Claude Desktop (see Installation section)
# Restart Claude Desktop after configuration
```

Then configure Claude Desktop as shown in the [Installation](#installation) section.

## Installation

### Prerequisites
- Docker and Docker Compose
- Claude Desktop app

### Setup with Claude Desktop

1. Clone this repository:
   ```bash
   git clone https://github.com/delexw/mcpware.git
   cd mcpware
   ```

2. Configure your backends in `config.json` (see Configuration section below)

3. Set up your environment variables:
   ```bash
   # Create a .env file with your tokens
   echo "GITHUB_PERSONAL_ACCESS_TOKEN=your_token_here" > .env
   ```

4. Build the Docker image:
   ```bash
   docker compose build
   ```

5. Add to Claude Desktop configuration:
   
   **Config file locations:**
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - Linux: `~/.config/Claude/claude_desktop_config.json`

   **Configuration:**
   ```json
   {
     "mcpServers": {
       "mcpware": {
         "command": "docker",
         "args": ["compose", "run", "--rm", "mcpware"],
         "cwd": "/path/to/mcpware",
         "env": {
           "GITHUB_PERSONAL_ACCESS_TOKEN": "your_github_token_here"
         }
       }
     }
   }
   ```

   **Important**: 
   - Replace `/path/to/mcpware` with the absolute path to your cloned repository
   - On Windows, use forward slashes or escaped backslashes: `C:/Users/YourName/mcpware`
   - Replace `your_github_token_here` with your actual GitHub Personal Access Token
   - You can also use environment variable references: `"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"` if you have it set in your system

   **Alternative: Using System Environment Variables**
   
   If you prefer to use system environment variables instead of hardcoding tokens:
   ```json
   {
     "mcpServers": {
       "mcpware": {
         "command": "docker",
         "args": ["compose", "run", "--rm", "mcpware"],
         "cwd": "/path/to/mcpware"
       }
     }
   }
   ```
   
   Then ensure your environment variables are set:
   - **macOS/Linux**: Add to `~/.zshrc` or `~/.bashrc`: `export GITHUB_PERSONAL_ACCESS_TOKEN=your_token_here`
   - **Windows**: Set via System Properties or PowerShell: `$env:GITHUB_PERSONAL_ACCESS_TOKEN="your_token_here"`

   **Alternative: Direct Docker Run (Without Docker Compose)**
   
   You can also configure mcpware using direct Docker commands:
   ```json
   {
     "mcpServers": {
       "mcpware": {
         "command": "docker",
         "args": [
           "run",
           "-i",
           "--rm",
           "-v",
           "/path/to/mcpware/config.json:/app/config.json:ro",
           "-v",
           "/var/run/docker.sock:/var/run/docker.sock",
           "-e",
           "GITHUB_PERSONAL_ACCESS_TOKEN",
           "mcpware"
         ],
         "env": {
           "GITHUB_PERSONAL_ACCESS_TOKEN": "your_github_token_here"
         }
       }
     }
   }
   ```
   
   This approach:
   - Uses absolute paths for mounting config.json
   - Doesn't require being in the mcpware directory
   - Passes environment variables directly to Docker

6. Restart Claude Desktop to load the new configuration

### Platform-Specific Docker Socket Configuration

The gateway needs access to the Docker socket to launch backend containers. The mount path differs by platform:

#### Quick Check
Run this script to check your Docker configuration:
```bash
python scripts/check_docker_socket.py
```

#### Linux/macOS/WSL2
No changes needed. The default configuration works:
```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

#### Windows (Native Containers)
Create a `docker-compose.override.yml` file:
```yaml
services:
  mcpware:
    volumes:
      - ./config.json:/app/config.json:ro
      - //./pipe/docker_engine://./pipe/docker_engine
```

#### Check Your Docker Type
To verify which Docker backend you're using on Windows:
```bash
docker version --format '{{.Server.Os}}'
```
- `linux` = WSL2/Hyper-V backend (use default config)
- `windows` = Windows containers (use override file)

## Configuration

Edit `config.json` to configure backend MCP servers:

```json
{
  "backends": [
    {
      "name": "github",
      "command": ["docker", "run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN", "ghcr.io/github/github-mcp-server"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN}"
      },
      "description": "GitHub MCP Server",
      "timeout": 30
    },
    {
      "name": "example",
      "command": ["npx", "-y", "@modelcontextprotocol/server-memory"],
      "description": "Example Memory MCP Server",
      "timeout": 30
    }
  ]
}
```

See `config.example.json` for a more comprehensive example with multiple backend servers including:
- GitHub MCP Server
- Time MCP Server
- Filesystem MCP Server
- Memory MCP Server
- Brave Search MCP Server

### Backend Configuration Options

- `name`: Unique identifier for the backend
- `command`: Command and arguments to launch the backend server
- `env`: Environment variables to pass to the backend (supports `${VAR}` substitution)
- `description`: Human-readable description
- `timeout`: Request timeout in seconds

## Usage

The gateway exposes two main tools:

### use_tool

Routes a tool call to a specific backend server.

Parameters:
- `backend_server`: Name of the backend server
- `server_tool`: Name of the tool to call
- `tool_arguments`: Arguments to pass to the tool

Example:
```json
{
  "backend_server": "github",
  "server_tool": "create_issue",
  "tool_arguments": {
    "owner": "myorg",
    "repo": "myrepo",
    "title": "New issue",
    "body": "Issue description"
  }
}
```

### discover_backend_tools

Discovers available backends and their tools.

Parameters:
- `backend_name`: (Optional) Specific backend to query

## Using mcpware Alongside Other MCP Servers

mcpware is designed to work alongside other MCP servers in your Claude Desktop configuration. You can:

1. **Use mcpware as a gateway** for multiple backend servers
2. **Keep some MCP servers separate** for direct access
3. **Mix and match** based on your needs

Example mixed configuration:
```json
{
  "mcpServers": {
    "mcpware": {
      "command": "docker",
      "args": ["compose", "run", "--rm", "mcpware"],
      "cwd": "/path/to/mcpware",
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "your_token"
      }
    },
    "redis-direct": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "-e", "REDIS_HOST=localhost", "mcp/redis"]
    }
  }
}
```

This allows you to:
- Access multiple servers through mcpware when you need routing
- Connect directly to specific servers when you need dedicated access
- Organize your MCP servers based on your workflow

## Development

### Running locally

```bash
python gateway_server.py --config config.json
```

### Docker

Build and run with Docker Compose:

```bash
# Build the image
docker compose build

# Run interactively (for testing)
docker compose run --rm mcpware

# View logs
docker compose logs -f mcpware

# Clean up
docker compose down
```

### Environment Variables

The gateway supports environment variable substitution in backend configurations. Set these in your `.env` file:

```bash
# Example .env file
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_xxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
# Add other tokens as needed
```

Environment variables referenced in `config.json` using `${VAR_NAME}` syntax will be automatically substituted.

## Testing

The project includes comprehensive unit and integration tests.

### Running Tests

1. Install test dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run all tests:
   ```bash
   pytest
   ```

3. Run tests with coverage:
   ```bash
   pytest --cov=src --cov=gateway_server --cov-report=html
   ```

4. Run specific test modules:
   ```bash
   pytest tests/test_config.py
   pytest tests/test_backend.py
   pytest tests/test_protocol.py
   ```

5. Run tests in watch mode:
   ```bash
   pytest-watch
   ```

### Verification Scripts

The project includes scripts to verify the gateway functionality:

```bash
# Test basic MCP functionality
python scripts/test_mcpware.py

# Verify backend tools discovery
python scripts/verify_backend_tools.py

# Test with Docker
docker compose run --rm -T mcpware < scripts/test_commands.txt
```

### Test Structure

- `tests/test_config.py` - Tests for configuration management
- `tests/test_backend.py` - Tests for backend process management and communication
- `tests/test_protocol.py` - Tests for MCP protocol handling
- `tests/test_gateway_server.py` - Integration tests for the complete system

### Coverage

The test suite aims for at least 80% code coverage. Coverage reports are generated in:
- Terminal output (with missing lines)
- `htmlcov/` directory (HTML report)
- `coverage.xml` (XML report for CI)

### Continuous Integration

Tests run automatically on GitHub Actions for:
- Multiple Python versions (3.8 - 3.12)
- Multiple operating systems (Ubuntu, Windows, macOS)
- Code linting with flake8 and black

## Architecture

The gateway:
1. Receives MCP requests via stdio
2. Launches and manages backend MCP server processes
3. Routes tool calls to appropriate backends
4. Returns responses to the client

## License

MIT
