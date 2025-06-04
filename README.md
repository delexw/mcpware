# mcpware - Gateway MCP Server

A Model Context Protocol (MCP) gateway server that routes tool calls to multiple stdio-based MCP backend servers.

## Overview

mcpware acts as a gateway/router for MCP, allowing AI agents to access multiple MCP servers through a single connection. It provides:

- **Single entry point**: Connect to multiple MCP servers through one gateway
- **Tool routing**: Routes tool calls to appropriate backend servers
- **Backend discovery**: Discover available backends and their tools
- **Process management**: Automatically launches and manages backend MCP server processes

## Installation

### Using with Claude Desktop

1. Clone this repository
2. Configure your backends in `config.json`
3. Build the Docker image:
   ```bash
   docker build -t mcpware-gateway .
   ```
4. Add to Claude Desktop configuration:
   ```json
   {
     "mcpServers": {
       "gateway": {
         "command": "docker",
         "args": ["run", "-i", "--rm", "-v", "./config.json:/app/config.json:ro", "mcpware-gateway"],
         "env": {
           "GITHUB_PERSONAL_ACCESS_TOKEN": "<YOUR_TOKEN>"
         }
       }
     }
   }
   ```

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

## Development

### Running locally

```bash
python gateway_server.py --config config.json
```

### Docker

Build and run with Docker:

```bash
# Build image
docker build -t mcpware-gateway .

# Run interactively
docker run -i --rm \
  -v ./config.json:/app/config.json:ro \
  -e GITHUB_PERSONAL_ACCESS_TOKEN=$GITHUB_PERSONAL_ACCESS_TOKEN \
  mcpware-gateway
```

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