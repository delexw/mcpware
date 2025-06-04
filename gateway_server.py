#!/usr/bin/env python3
"""
Gateway MCP Server
Routes tool calls to multiple stdio-based MCP backend servers
"""
import argparse
import logging
import sys
import json
import asyncio
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point for stdio mode"""
    logger.info("Gateway MCP Server starting in stdio mode")
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="Gateway MCP Server")
    parser.add_argument(
        "--config",
        default="config.json",
        help="Configuration file path (default: config.json)"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Import components
    from src.protocol import JSONRPCHandler, MCPProtocolHandler
    from src.config import ConfigurationManager
    from src.backend import BackendForwarder
    
    # Initialize components
    config_manager = ConfigurationManager(args.config)
    config_manager.backends = config_manager.load()
    
    # Convert backends to dictionary format for BackendForwarder
    backend_configs = []
    for backend in config_manager.backends.values():
        config = {
            "name": backend.name,
            "command": backend.command,
            "description": backend.description,
            "timeout": backend.timeout,
            "env": backend.env
        }
        backend_configs.append(config)
    
    backend_forwarder = BackendForwarder(backend_configs)
    await backend_forwarder.initialize()
    
    protocol_handler = MCPProtocolHandler(config_manager, backend_forwarder)
    jsonrpc_handler = JSONRPCHandler(protocol_handler)
    
    try:
        # Read from stdin and write to stdout
        while True:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break
                
            line = line.strip()
            if not line:
                continue
                
            try:
                data = json.loads(line)
                response = await jsonrpc_handler.handle_request(data)
                print(json.dumps(response))
                sys.stdout.flush()
            except json.JSONDecodeError:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": "Parse error"
                    }
                }
                print(json.dumps(error_response))
                sys.stdout.flush()
                
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await backend_forwarder.close()


if __name__ == "__main__":
    asyncio.run(main()) 