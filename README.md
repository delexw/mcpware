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

**How it works**: mcpware runs inside a Docker container and launches other MCP servers as Docker containers. When you request a tool from a backend, mcpware:
1. Starts the backend's Docker container (if not already running)
2. Communicates with it via stdio (standard input/output)
3. Routes your request to the appropriate backend
4. Returns the response back to Claude

The Docker socket mount (`/var/run/docker.sock`) gives mcpware access to the host's Docker daemon, allowing it to create and manage backend containers.

**Important limitation**: When running mcpware in Docker (as shown in this guide), backend MCP servers MUST be Docker containers. NPM-based backends (like `npx @modelcontextprotocol/server-memory`) are NOT supported because:
- mcpware's container doesn't have Node.js installed
- File paths would be isolated to the container
- Process communication across the container boundary doesn't work for non-Docker processes

To use NPM-based backends, you would need to run mcpware directly on your host machine (not covered in this guide).

## Quick Start

```bash
# Clone the repository
git clone https://github.com/delexw/mcpware.git
cd mcpware

# Build the Docker image
docker build -t mcpware .

# Configure Claude Desktop (see Installation section)
# Add the configuration to claude_desktop_config.json
# Restart Claude Desktop after configuration
```

Then configure Claude Desktop as shown in the [Installation](#installation) section.

## Installation

### Prerequisites
- Docker
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

4. Add to Claude Desktop configuration:
   
   **Config file locations:**
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - Linux: `~/.config/Claude/claude_desktop_config.json`

   **Configuration (Direct Docker Run):**
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

   **Important**: 
   - Replace `/path/to/mcpware` with the absolute path to your cloned repository
   - Replace `your_github_token_here` with your actual GitHub Personal Access Token
   - The Docker socket mount (`/var/run/docker.sock`) is required for mcpware to launch Docker-based backends
   
   **Why mount the Docker socket?**
   - mcpware needs to launch Docker containers for backend MCP servers (like `ghcr.io/github/github-mcp-server`)
   - The Docker socket mount allows mcpware to communicate with Docker
   - Without this mount, mcpware cannot start backend servers that run as Docker containers

6. Restart Claude Desktop to load the new configuration

### Platform-Specific Docker Socket Configuration

The gateway needs access to the Docker socket to launch backend containers. The mount path differs by platform:

**Why is Docker socket access required?**
mcpware acts as a process manager that launches backend MCP servers. When a backend is configured to run as a Docker container (e.g., `ghcr.io/github/github-mcp-server`), mcpware needs to:
- Create and start Docker containers
- Manage their lifecycle (stop/restart)
- Communicate with them via stdio

Without Docker socket access, mcpware cannot launch Docker-based backends and will fail with permission errors.

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
Update the Docker socket path in your Claude Desktop configuration:
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
        "//./pipe/docker_engine://./pipe/docker_engine",
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

Note the different Docker socket path: `//./pipe/docker_engine` instead of `/var/run/docker.sock`

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
      "name": "time",
      "command": ["docker", "run", "-i", "--rm", "mcp/time"],
      "description": "Time MCP Server",
      "timeout": 30
    }
  ]
}
```

**Note**: When running mcpware in Docker (as shown in this guide), only Docker-based backend servers are supported. The backend commands must start with `["docker", "run", ...]`. NPM-based backends (like `npx` commands) are only supported when running mcpware directly on the host machine.

See `config.example.json` for a more comprehensive example with Docker-based backend servers:
- GitHub MCP Server
- Time MCP Server

### Example: Connecting to Host Services

Here's a comprehensive example showing how to configure backends that connect to services running on your host machine:

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
      "name": "local-mysql",
      "command": [
        "docker", "run", "-i", "--rm",
        "bytebase/dbhub",
        "--transport", "stdio",
        "--dsn", "mysql://root:password@host.docker.internal:3306/myapp?sslmode=disable"
      ],
      "description": "Local MySQL Database",
      "timeout": 30
    },
    {
      "name": "local-postgres", 
      "command": [
        "docker", "run", "-i", "--rm",
        "dbhub/postgres",
        "--dsn", "postgres://user:pass@host.docker.internal:5432/mydb"
      ],
      "description": "Local PostgreSQL Database",
      "timeout": 30
    },
    {
      "name": "local-redis",
      "command": [
        "docker", "run", "-i", "--rm",
        "mcp/redis",
        "--host", "host.docker.internal",
        "--port", "6379"
      ],
      "description": "Local Redis Instance",
      "timeout": 30
    }
  ]
}
```

In this configuration:
- `host.docker.internal` resolves to your host machine's IP address
- Backend containers can connect to any service listening on host ports
- This works because backends are sibling containers, not nested children

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
      "args": [
        "run", "-i", "--rm",
        "-v", "/path/to/mcpware/config.json:/app/config.json:ro",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
        "mcpware"
      ],
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

Build and run with Docker:

```bash
# Build the image
docker build -t mcpware .

# Run interactively (for testing)
docker run -it --rm \
  -v $(pwd)/config.json:/app/config.json:ro \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e GITHUB_PERSONAL_ACCESS_TOKEN \
  mcpware

# Run with specific config file
docker run -it --rm \
  -v /path/to/your/config.json:/app/config.json:ro \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e GITHUB_PERSONAL_ACCESS_TOKEN \
  mcpware
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
docker run -it --rm \
  -v $(pwd)/config.json:/app/config.json:ro \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e GITHUB_PERSONAL_ACCESS_TOKEN \
  mcpware < scripts/test_commands.txt
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
1. Receives MCP requests via stdio from Claude Desktop
2. Identifies which backend should handle the request
3. Launches the backend's Docker container (if needed)
4. Forwards the request to the backend via stdio
5. Returns the backend's response to Claude Desktop

### Container Architecture

When running in Docker, mcpware uses a "Docker-out-of-Docker" approach:
- mcpware runs in its own container
- It accesses the host's Docker daemon through the mounted socket
- Backend containers are created as siblings (not children) on the host
- Communication happens through stdio pipes between containers

This is different from true "Docker-in-Docker" and is more secure and efficient.

#### Accessing Host Services from Backend Containers

Because backend containers are created as siblings (not children) of the mcpware container, they can access services running on the host machine using `host.docker.internal`. This is particularly useful for:

- **Local databases**: Connect to MySQL, PostgreSQL, Redis, etc. running on your host
- **Development services**: Access local API servers, mock services, or other tools
- **Shared resources**: Connect to any service listening on host ports

**Example**: A database backend configuration connecting to host MySQL:
```json
{
  "name": "local-mysql",
  "command": [
    "docker", "run", "-i", "--rm",
    "dbhub/mysql-mcp-server",
    "--dsn", "mysql://user:pass@host.docker.internal:3306/mydb"
  ],
  "description": "Local MySQL Database"
}
```

This architecture means backend containers have the same networking capabilities as any container started directly with `docker run`, making it easy to integrate with your local development environment.

### Limitations of Container-Based Deployment

The containerized deployment has these constraints:
- **Only Docker backends**: Backend commands must start with `["docker", "run", ...]`
- **No NPM/host tools**: The mcpware container lacks Node.js, Python, etc.
- **Isolated filesystem**: Container can't access host files directly
- **Network isolation**: Can't communicate with host processes via stdio

For maximum flexibility (NPM backends, host tools), run mcpware directly on the host machine instead of in Docker.

## License

MIT