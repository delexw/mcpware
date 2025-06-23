#!/usr/bin/env python3
"""
mcpware
Routes tool calls to multiple stdio-based MCP backend servers
"""
import argparse
import asyncio
import json
import logging
import signal
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.backend import BackendForwarder
from src.config import ConfigurationManager
from src.protocol import JSONRPCHandler, MCPProtocolHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def setup_components(config_path: Path) -> Tuple[ConfigurationManager, BackendForwarder, MCPProtocolHandler, JSONRPCHandler]:
    """Initialize and setup all components.
    
    Returns:
        Tuple of (config_manager, backend_forwarder, protocol_handler, jsonrpc_handler)
    """
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
    jsonrpc_handler: JSONRPCHandler,
    backend_forwarder: BackendForwarder,
    backends_initialized: bool
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """Process a single request line.
    
    Args:
        line: JSON-RPC request line to process
        jsonrpc_handler: Handler for JSON-RPC protocol
        backend_forwarder: Forwarder for backend communication
        backends_initialized: Flag indicating if backends are initialized
    
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
    _, backend_forwarder, _, jsonrpc_handler = await setup_components(args.config)
    
    # Flag to track if backends are initialized
    backends_initialized = False
    
    # Setup signal handlers for proper Docker shutdown
    shutdown_event = asyncio.Event()
    
    def signal_handler(signum: int, _) -> None:
        logger.info(f"Received signal {signum}, initiating shutdown...")
        shutdown_event.set()
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Read from stdin and write to stdout
        loop = asyncio.get_event_loop()
        
        # Create an async stdin reader using asyncio streams
        stdin_reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(stdin_reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        
        # Create a task for reading stdin
        async def read_stdin() -> None:
            nonlocal backends_initialized
            while not shutdown_event.is_set():
                try:
                    # Use asyncio timeout to make stdin reading cancellable
                    line_bytes = await asyncio.wait_for(
                        stdin_reader.readline(),
                        timeout=1.0  # Check for shutdown every second
                    )
                    
                    # Check for EOF - empty bytes from readline indicates stdin was closed
                    if not line_bytes:
                        logger.info("Stdin closed - client disconnected, initiating shutdown")
                        shutdown_event.set()
                        break
                    
                    line = line_bytes.decode().strip()
                    if not line:
                        continue
                    
                    response, backends_initialized = await process_request(
                        line, jsonrpc_handler, backend_forwarder, backends_initialized
                    )
                    
                    if response:
                        print(json.dumps(response))
                        sys.stdout.flush()
                        
                except asyncio.TimeoutError:
                    # Timeout is expected - just continue to check shutdown_event
                    continue
                except Exception as e:
                    if shutdown_event.is_set():
                        break
                    logger.error(f"Error reading stdin: {e}")
                    break
        
        # Run stdin reading until shutdown signal
        stdin_task = asyncio.create_task(read_stdin())
        
        # Wait for either stdin task to complete or shutdown signal
        shutdown_task = asyncio.create_task(shutdown_event.wait())
        _, pending = await asyncio.wait(
            [stdin_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        logger.info("Main loop exiting, cancelling remaining tasks...")
        
        # Cancel any remaining tasks
        for task in pending:
            logger.debug(f"Cancelling task: {task}")
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        
        logger.info("All tasks cancelled, proceeding to cleanup...")
                
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    finally:
        # Ensure proper cleanup of backend processes according to MCP specification
        if backends_initialized:
            logger.info("Cleaning up backend MCP servers...")
            try:
                # Add timeout to prevent hanging indefinitely
                await asyncio.wait_for(backend_forwarder.close(), timeout=30.0)
                logger.info("Backend cleanup completed successfully")
            except asyncio.TimeoutError:
                logger.error("Backend cleanup timed out after 30 seconds")
            except Exception as e:
                logger.error(f"Error during backend cleanup: {e}")
        else:
            logger.info("No backends were initialized, skipping cleanup")
        
        logger.info("Gateway server shutdown complete")


if __name__ == "__main__":
    asyncio.run(main()) 