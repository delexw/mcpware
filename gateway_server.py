#!/usr/bin/env python3
"""
mcpware
Routes tool calls to multiple stdio-based MCP backend servers
"""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def setup_components(config_path: Path) -> tuple:
    """Initialize and setup all components.
    
    Returns:
        Tuple of (config_manager, backend_forwarder, protocol_handler, jsonrpc_handler)
    """
    from src.backend import BackendForwarder
    from src.config import ConfigurationManager
    from src.protocol import JSONRPCHandler, MCPProtocolHandler
    
    # Initialize components
    config_manager = ConfigurationManager(str(config_path))
    config_manager.backends = config_manager.load()
    
    # Pass backends directly as BackendMCPConfig objects
    backend_forwarder = BackendForwarder(list(config_manager.backends.values()))
    protocol_handler = MCPProtocolHandler(config_manager, backend_forwarder)
    jsonrpc_handler = JSONRPCHandler(protocol_handler)
    
    return config_manager, backend_forwarder, protocol_handler, jsonrpc_handler


async def process_request(
    line: str,
    jsonrpc_handler: 'JSONRPCHandler',
    backend_forwarder: 'BackendForwarder',
    backends_initialized: bool
) -> tuple[Optional[Dict[str, Any]], bool]:
    """Process a single request line.
    
    Returns:
        Tuple of (response, backends_initialized)
    """
    try:
        data = json.loads(line)
        
        # Initialize backends on first valid request using walrus operator
        if not backends_initialized and (method := data.get("method")):
            logger.info(f"Initializing backends on first request: {method}")
            await backend_forwarder.initialize()
            backends_initialized = True
        
        response = await jsonrpc_handler.handle_request(data)
        
        # Only return response if the original request had an id (not a notification)
        if "id" in data and response is not None:
            return response, backends_initialized
            
    except json.JSONDecodeError:
        # For parse errors, check if it looks like a JSON-RPC request
        if line.startswith('{') and any(key in line for key in ('jsonrpc', 'method')):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                }
            }, backends_initialized
        else:
            logger.warning(f"Ignoring non-JSON input: {line[:50]}...")
    
    return None, backends_initialized


async def main() -> None:
    """Main entry point for stdio mode"""
    logger.info("mcpware starting in stdio mode")
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="mcpware")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.json"),
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
    
    # Setup components
    config_manager, backend_forwarder, protocol_handler, jsonrpc_handler = await setup_components(args.config)
    
    # Flag to track if backends are initialized
    backends_initialized = False
    
    try:
        # Read from stdin and write to stdout
        loop = asyncio.get_event_loop()
        while line := await loop.run_in_executor(None, sys.stdin.readline):
            line = line.strip()
            if not line:
                continue
            
            response, backends_initialized = await process_request(
                line, jsonrpc_handler, backend_forwarder, backends_initialized
            )
            
            if response:
                print(json.dumps(response))
                sys.stdout.flush()
                
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        if backends_initialized:
            await backend_forwarder.close()


if __name__ == "__main__":
    asyncio.run(main()) 