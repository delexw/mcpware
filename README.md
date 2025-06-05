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

## 🎯 Key Features

### 🚀 Bypass Tool Limits
- **Problem**: Cursor has a 40-80 tool limit per MCP server
- **Solution**: mcpware exposes only 2 routing tools while providing access to unlimited backend tools
- **Result**: Connect to GitHub (50+ tools), databases, and more through a single gateway!

### 🔒 Built-in Security
- **Prevents cross-backend data leakage** (e.g., database → GitHub)
- **Blocks SQL injection and sensitive data exposure**
- **Taint tracking** stops all access after suspicious activity
- **Mandatory security classification** for each backend (public/internal/sensitive)

### 🔧 Additional Benefits
- **Single entry point** for multiple MCP servers
- **Automatic process management** for backend servers
- **Docker-based** isolation and deployment

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

## How it Works

mcpware runs as a Docker container that:
1. Receives requests from Claude Desktop via stdio
2. Routes them to the appropriate backend MCP server (also running in Docker)
3. Returns responses back to Claude

**Important**: Backend servers must be Docker containers when running mcpware in Docker. NPM-based backends require running mcpware on the host.

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

Create a `config.json` with your backend servers:

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
    }
  ],
  "security_policy": {
    "backend_security_levels": {
      "github": "public"
    }
  }
}
```

**Required**:
- `security_policy` with `backend_security_levels` classifying each backend as `public`, `internal`, or `sensitive`
- Backend commands must start with `["docker", "run", ...]` when using Docker

See `config.example.json` for more backend examples (databases, APIs, etc.).

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

## Security Details

mcpware prevents cross-backend information leakage through multiple layers:

### Attack Prevention Example
1. **Attacker** creates malicious GitHub issue with prompt injection
2. **User** asks: "Review my GitHub issues"  
3. **Agent** reads malicious issue and tries to query database
4. **mcpware blocks**: Cannot send database data back to GitHub (public backend)

### Security Tools
- Use `security_status` tool to monitor session security
- Configure policies in `config.json` (see `config.example.json` for full options)
- Automatic taint tracking after suspicious activity

## Architecture

mcpware uses a "Docker-out-of-Docker" approach:
- Runs as a container with access to host Docker daemon
- Launches backend containers as siblings (not children)
- Backends can access host services via `host.docker.internal`
- Communication via stdio pipes between containers

## License

MIT