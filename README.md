# Gateway MCP Server

A gateway MCP server that routes tool calls to multiple HTTP-based MCP backend servers running in Docker containers.

## Features

- 🔄 **Single Gateway Interface**: Connect to multiple Docker-based MCP servers through one gateway
- 🎯 **Simple Routing**: Two tools - `use_tool` to route calls and `discover_backend_tools` to explore backends
- 🐳 **Docker Integration**: Forward requests to HTTP-based MCP servers in Docker containers
- 🔧 **MCP Client Compatible**: Works with Claude Desktop and other MCP clients

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Backends

Edit `config.json` to point to your Docker-based MCP servers:

```json
{
  "backends": [
    {
      "name": "database",
      "url": "http://localhost:8001",
      "description": "Database MCP Server",
      "timeout": 30,
      "headers": {
        "Authorization": "Bearer ${DB_API_TOKEN}"
      }
    },
    {
      "name": "custom",
      "url": "http://localhost:8002", 
      "description": "Custom MCP Server",
      "timeout": 30
    }
  ]
}
```

### 3. Configure in Claude Desktop

Add to your Claude Desktop configuration:

#### macOS
`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gateway": {
      "command": "python",
      "args": ["/path/to/gateway_server.py"],
      "env": {
        "DB_API_TOKEN": "your-token"
      }
    }
  }
}
```

#### Windows
`%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gateway": {
      "command": "python",
      "args": ["C:\\path\\to\\gateway_server.py"],
      "env": {
        "DB_API_TOKEN": "your-token"
      }
    }
  }
}
```

## How It Works

The gateway exposes two tools:

1. **`use_tool`** - Routes tool calls to backend servers
   - `backend_server`: Name of the backend (e.g., "database")
   - `server_tool`: Tool name on that backend
   - `tool_arguments`: Arguments for the tool

2. **`discover_backend_tools`** - Discovers available backends and their tools
   - `backend_server` (optional): Specific backend to query

## Environment Variables

The gateway supports environment variable substitution in configuration:
- Use `${VARIABLE_NAME}` in config.json
- Set variables when configuring the MCP client

## License

MIT License